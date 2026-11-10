"""One-command relay audit: run the audit, build a scorecard, render HTML."""
import argparse
import contextlib
import html
import io
import json
from pathlib import Path

from . import protocol_audit, protocol_scorecard
from .evidence import ContractError, read_json, save, stamp, write_manifest

SCHEMA = 'relay-audit-report-v1'


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--name')
    parser.add_argument('--from-audit', type=Path,
                        help='build a report from an existing audit evidence directory')
    parser.add_argument('--base-url')
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--api-key-file', type=Path)
    parser.add_argument('--api-key-env')
    parser.add_argument('--allow-local', action='store_true')
    parser.add_argument('--enable-remote', action='store_true')
    parser.add_argument('--mode', choices=('auto', 'responses', 'chat'), default='auto')
    parser.add_argument('--catalog-mode', choices=('target', 'sample'), default='target')
    parser.add_argument('--exclude-model', action='append', default=[])
    return parser


def _load_audit(path):
    root = Path(path)
    plan = read_json(root / 'PLAN.json')
    summary = read_json(root / 'SUMMARY.json')
    return plan, summary.get('results') or {}, summary.get('verdict') or {}


def _cell(value):
    if value['status'] == 'n/a':
        return 'n/a'
    sample = value.get('sample')
    suffix = f" ({sample})" if sample else ''
    return f"{value['status']} {value['coverage']}%{suffix}"


def _observations(results):
    meta = results.get('_meta') or {}
    mode = meta.get('mode', 'responses')
    if mode == 'chat':
        chat = results.get('chat') or {}
        stream = results.get('chat_stream') or {}
        tools = results.get('chat_tools') or {}
        choices = ((tools.get('json') or {}).get('choices') or [])
        calls = ((choices[0].get('message') or {}).get('tool_calls') or []) if choices else []
        structured = protocol_audit._chat_content(results.get('chat_structured') or {})
        vision = protocol_audit._chat_content(results.get('chat_vision') or {})
        return [('模式', 'chat'),
                ('Chat 状态', str(chat.get('status'))),
                ('流式结束', str(stream.get('finish_reason'))),
                ('工具调用', str(len(calls))),
                ('结构化输出', structured[:160] or '-'),
                ('视觉', vision[:80] or '-'),
                ('usage 重复', str([((item.get('json') or {}).get('usage') or {}).get('prompt_tokens')
                                   for item in results.get('usage_repeat') or []])),
                ('目录抽检', json.dumps(results.get('catalog_liveness'), ensure_ascii=False))]
    summary = (results.get('responses_min') or {}).get('summary') or {}
    return [('模式', 'responses'),
            ('Responses 状态', str((results.get('responses_min') or {}).get('status'))),
            ('输出类型', str(summary.get('output_types'))),
            ('instructions', f"{summary.get('instructions_len')} 字符"),
            ('usage', json.dumps(summary.get('usage'), ensure_ascii=False)),
            ('reasoning low/high',
             f"{(results.get('effort_low', {}).get('summary', {}).get('usage') or {}).get('reasoning_tokens')}"
             f" / "
             f"{(results.get('effort_high', {}).get('summary', {}).get('usage') or {}).get('reasoning_tokens')}"),
            ('目录抽检', json.dumps(results.get('catalog_liveness'), ensure_ascii=False)),
            ('store', f"min={(results.get('responses_min', {}).get('summary') or {}).get('store')}；"
                      f"prev_first={(results.get('prev_first', {}).get('summary') or {}).get('store')}")]


def render_html(plan, results, verdict, scorecard, source):
    esc = html.escape
    target = scorecard['targets'][0]
    meta = results.get('_meta') or {}
    mode = meta.get('mode', 'responses')
    status = verdict.get('status', 'unknown')
    overall = target['overall']
    level_class = {'pass': 'pass', 'warn': 'warn', 'fail': 'fail',
                   'info': 'info', 'n/a': 'na'}

    def badge(level, label=None):
        return (f'<span class="badge {level_class.get(level, "na")}">'
                f'{esc(label or level)}</span>')

    grade_level = {'A': 'pass', 'B': 'pass', 'C': 'warn', 'D': 'fail'}
    status_level = {'consistent': 'pass', 'partial': 'warn', 'inconsistent': 'fail'}
    cards = [
        ('协议面', badge(status_level.get(status, 'na'), status)),
        ('可用性', badge(grade_level.get(overall['grade'], 'na'),
                       overall['grade'] + (f" ({overall['coverage']}%)"
                                           if overall['coverage'] is not None else ''))),
        ('型号身份', badge('n/a', '无法判定')),
    ]
    card_html = ''.join(f'<div class="card"><div class="label">{esc(label)}</div>'
                        f'<div class="value">{value}</div></div>'
                        for label, value in cards)

    main_labels = [item['label'] for item in scorecard['dimensions']]
    main_head = ''.join(f'<th>{esc(label)}</th>' for label in main_labels)
    main_cells = ''.join(f'<td>{esc(_cell(target["dimensions"][spec["key"]]))}</td>'
                         for spec in scorecard['dimensions'])
    main_row = f'<tr><td>{esc(target["name"])}</td><td>{esc(target.get("model") or "")}</td>{main_cells}<td>{esc(overall["grade"])}</td></tr>'

    app_labels = [item['label'] for item in scorecard['appendix']]
    app_head = ''.join(f'<th>{esc(label)}</th>' for label in app_labels)
    app_cells = ''.join(f'<td>{esc(_cell(target["appendix"][spec["key"]]))}</td>'
                        for spec in scorecard['appendix'])

    findings = ''.join(
        f'<tr><td><code>{esc(item["code"])}</code></td>'
        f'<td>{badge(item["level"])}</td><td>{esc(item["message"])}</td></tr>'
        for item in verdict.get('findings') or [])
    observations = ''.join(f'<div class="obs"><div class="k">{esc(key)}</div>'
                           f'<div class="v">{esc(value)}</div></div>'
                           for key, value in _observations(results))
    evidence = ', '.join(sorted(
        p.name for p in Path(source).iterdir() if p.is_file())) if Path(source).is_dir() else '-'
    generated = meta.get('started_asia') or stamp()
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中转查 · 协议面审计 — {esc(target["name"])}</title>
<style>
:root {{ --bg:#f6f7f9; --panel:#fff; --ink:#1f2328; --muted:#667085; --line:#e4e7ec;
         --pass:#137a4b; --warn:#a15c00; --fail:#b42318; --info:#475467; --na:#98a2b3; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
        font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:32px 20px 64px; }}
header {{ margin-bottom:24px; }}
h1 {{ font-size:28px; margin:0 0 8px; letter-spacing:-.02em; }}
.meta {{ color:var(--muted); font-size:14px; }}
.meta span {{ margin-right:16px; white-space:nowrap; }}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:20px 0 28px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
         padding:16px 18px; }}
.label {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
.value {{ font-size:22px; font-weight:650; }}
.badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:13px;
          font-weight:600; }}
.badge.pass {{ background:#e7f6ee; color:var(--pass); }}
.badge.warn {{ background:#fff4e5; color:var(--warn); }}
.badge.fail {{ background:#fee4e2; color:var(--fail); }}
.badge.info, .badge.na {{ background:#eef0f3; color:var(--info); }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
           padding:20px; margin-bottom:18px; }}
.intro {{ border-left:3px solid #1f5fbf; background:linear-gradient(135deg,#f8fbff,#fff); }}
.lede {{ font-size:16px; margin:0 0 6px; }}
h2 {{ font-size:18px; margin:0 0 14px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th, td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line);
          vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; background:#fafbfc; }}
tr:last-child td {{ border-bottom:0; }}
code {{ background:#f2f4f7; border-radius:5px; padding:1px 5px; font-size:13px; }}
.obs {{ display:grid; grid-template-columns:180px 1fr; gap:8px; padding:7px 0;
        border-bottom:1px dashed var(--line); }}
.obs:last-child {{ border-bottom:0; }}
.obs .k {{ color:var(--muted); }}
.note {{ color:var(--muted); font-size:13px; }}
footer {{ color:var(--muted); font-size:12px; margin-top:24px; }}
footer a {{ color:#1f5fbf; text-decoration:none; }}
footer .brand {{ margin-top:6px; }}
@media (max-width:720px) {{ .cards {{ grid-template-columns:1fr; }} .obs {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; }} section, .card {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>中转查 · 协议面审计</h1>
  <div class="meta">
    <span>目标：{esc(plan.get('base_url') or '')}</span>
    <span>型号：{esc(plan.get('model') or '')}</span>
    <span>模式：{esc(mode)}</span>
    <span>生成：{esc(generated)}</span>
  </div>
</header>
<section class="intro">
  <p class="lede">这是中转查对 <strong>{esc(target["name"])}</strong> 的协议面与可用性快照。
  它只回答“能不能用、协议面是否像官方”，不认证型号身份。</p>
  <p class="note">主分只看稳定性、对话、能力、目录；协议契约、错误码和包装在附录，不计入主分。</p>
</section>
<div class="cards">{card_html}</div>
<section>
  <h2>可用性记分卡</h2>
  <table><thead><tr><th>目标</th><th>型号</th>{main_head}<th>总分</th></tr></thead>
  <tbody>{main_row}</tbody></table>
  <p class="note">主分只看能不能用：稳定性、对话、能力、目录；协议细节在下面附录，不计入主分。</p>
</section>
<section>
  <h2>附录：协议细节（不计入主分）</h2>
  <table><thead><tr><th>目标</th>{app_head}</tr></thead>
  <tbody><tr><td>{esc(target["name"])}</td>{app_cells}</tr></tbody></table>
</section>
<section>
  <h2>检查明细</h2>
  <table><thead><tr><th>检查</th><th>结果</th><th>说明</th></tr></thead>
  <tbody>{findings}</tbody></table>
</section>
<section>
  <h2>关键观测</h2>
  {observations}
</section>
<section>
  <h2>证据</h2>
  <p class="note">源目录：<code>{esc(str(source))}</code></p>
  <p class="note">文件：{esc(evidence)}</p>
</section>
<footer>
  本报告只验证协议面/可用性，不认证型号身份；低分不等于型号假，高分也不等于型号真。
  同门型号替换不在覆盖范围内。
  <div class="brand">由 <a href="https://zhongzhuancha.com/">中转查</a> 生成。</div>
</footer>
</div>
</body>
</html>
'''


def run(args):
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    if args.from_audit:
        plan, results, verdict = _load_audit(args.from_audit)
        source = str(Path(args.from_audit).resolve())
        args.out.mkdir(parents=True, mode=0o700)
    else:
        if not args.enable_remote:
            print(json.dumps({'status': 'dry_run', 'requests': 25,
                              'note': 'pass --enable-remote to send'}, ensure_ascii=False))
            return 0
        args.out.mkdir(parents=True, mode=0o700)
        audit_out = args.out / 'AUDIT'
        namespace = argparse.Namespace(
            out=audit_out, base_url=args.base_url, model=args.model,
            api_key_file=args.api_key_file, api_key_env=args.api_key_env,
            allow_local=args.allow_local, enable_remote=True, verify=None,
            exclude_model=args.exclude_model, catalog_mode=args.catalog_mode,
            mode=args.mode)
        with contextlib.redirect_stdout(io.StringIO()):
            protocol_audit.run(namespace)
        plan = read_json(audit_out / 'PLAN.json')
        stored = read_json(audit_out / 'SUMMARY.json')
        results = stored.get('results') or {}
        verdict = stored.get('verdict') or {}
        source = str(audit_out.resolve())

    name = args.name or plan.get('base_url') or 'relay'
    scorecard = protocol_scorecard.build({'targets': [{
        'name': name, 'model': plan.get('model'),
        'status': verdict.get('status'), 'findings': verdict.get('findings') or []}]})
    save(args.out / 'SCORECARD.json', scorecard)
    (args.out / 'SCORECARD.md').write_text(protocol_scorecard.render(scorecard),
                                           encoding='utf-8')
    (args.out / 'REPORT.html').write_text(
        render_html(plan, results, verdict, scorecard, source), encoding='utf-8')
    save(args.out / 'SUMMARY.json', {
        'schema': SCHEMA, 'name': name, 'target': plan.get('base_url'),
        'model': plan.get('model'), 'mode': (results.get('_meta') or {}).get('mode'),
        'status': verdict.get('status'), 'verdict': verdict,
        'scorecard': scorecard, 'source': source})
    write_manifest(args.out)
    print(json.dumps({'status': verdict.get('status'),
                      'scorecard': scorecard['targets'][0]['overall'],
                      'report': str((args.out / 'REPORT.html').resolve()),
                      'identity_authenticated': False}, ensure_ascii=False))
    return 2 if verdict.get('status') == 'inconsistent' else 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ContractError as error:
        print(json.dumps({'status': 'error', 'error_type': 'ContractError',
                          'message': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

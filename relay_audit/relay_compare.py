"""Compare multiple relay audit evidence directories in one HTML page."""
import argparse
import html
import json
from pathlib import Path

from . import protocol_scorecard
from .evidence import ContractError, read_json, save, stamp, write_manifest
from .html_meta import SITE_URL, meta_tags

SCHEMA = 'relay-compare-v1'
HARD = {
    'responses.surface', 'chat.surface', 'output.cap', 'previous.roundtrip',
    'invalid.parameter', 'error.invalid_model', 'error.invalid_cap',
    'error.unauthorized', 'image.vision', 'tools.function_call', 'structured.output',
}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--audit', type=Path, action='append', default=[])
    return parser


def load_specs(args):
    if args.config:
        try:
            doc = json.loads(Path(args.config).read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ContractError('invalid compare config') from error
        targets = doc.get('targets') if isinstance(doc, dict) else None
        if not isinstance(targets, list) or not targets:
            raise ContractError('config needs a non-empty targets list')
        specs = []
        for item in targets:
            if not isinstance(item, dict) or not item.get('audit'):
                raise ContractError('each target needs audit')
            specs.append({'name': item.get('name'), 'audit': Path(item['audit'])})
        return specs
    if not args.audit:
        raise ContractError('--config or --audit is required')
    return [{'name': path.name, 'audit': path} for path in args.audit]


def build_rows(specs):
    rows = []
    for spec in specs:
        root = Path(spec['audit'])
        plan = read_json(root / 'PLAN.json')
        summary = read_json(root / 'SUMMARY.json')
        verdict = summary.get('verdict') or {}
        results = summary.get('results') or {}
        name = spec.get('name') or root.name
        findings = verdict.get('findings') or []
        card = protocol_scorecard.build({'targets': [{
            'name': name, 'model': plan.get('model'),
            'status': verdict.get('status'), 'findings': findings}]})
        target = card['targets'][0]
        hard = [item['code'] for item in findings
                if item.get('level') == 'fail' and item.get('code') in HARD]
        min_summary = (results.get('responses_min') or {}).get('summary') or {}
        rows.append({
            'name': name,
            'base_url': plan.get('base_url'),
            'model': plan.get('model'),
            'mode': (results.get('_meta') or {}).get('mode'),
            'instructions_len': min_summary.get('instructions_len'),
            'instructions_sha256': min_summary.get('instructions_sha256'),
            'instructions_head': min_summary.get('instructions_head'),
            'protocol': verdict.get('status'),
            'usability': target['overall'],
            'dimensions': {key: value for key, value in target['dimensions'].items()},
            'appendix': {key: value for key, value in target['appendix'].items()},
            'hard_fails': hard,
            'warns': sum(item.get('level') == 'warn' for item in findings),
            'source': str(root.resolve()),
        })
    return rows


def _cell(value):
    if value['status'] == 'n/a':
        return 'n/a'
    sample = value.get('sample')
    suffix = f" ({sample})" if sample else ''
    return f"{value['status']} {value['coverage']}%{suffix}"


def _wrapper_section(rows):
    esc = html.escape
    groups = {}
    for row in rows:
        sha = row.get('instructions_sha256')
        if sha:
            groups.setdefault(sha, []).append(row)
    items = []
    for sha, members in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        names = ' / '.join(esc(item['name']) for item in members)
        length = members[0].get('instructions_len')
        head = (members[0].get('instructions_head') or '').replace('\n', ' ')[:80]
        label = f'同源 {len(members)} 个' if len(members) > 1 else '单独包装'
        items.append(f'<li><strong>{label}</strong>：{names}；'
                     f'{esc(str(length))} 字符；sha <code>{esc(sha[:12])}…</code>；'
                     f'head “{esc(head)}”</li>')
    if not items:
        return ''
    return ('<section><h2>同源包装</h2><ul class="wrap-list">'
            + ''.join(items) + '</ul>'
            '<p class="note">相同 instructions 哈希通常意味着同一个上游/同一套壳；'
            '这是线索，不是型号认证。</p></section>')


def render_html(rows):
    esc = html.escape
    total = len(rows)
    usable_a = sum(row['usability']['grade'] == 'A' for row in rows)
    protocol_bad = sum(row['protocol'] == 'inconsistent' for row in rows)

    def badge_level(value):
        return {'pass': 'pass', 'warn': 'warn', 'fail': 'fail',
                'consistent': 'pass', 'partial': 'warn',
                'inconsistent': 'fail', 'a': 'pass', 'b': 'pass',
                'c': 'warn', 'd': 'fail'}.get(value, 'na')

    body = []
    for row in rows:
        dims = row['dimensions']
        cells = ''.join(f'<td>{esc(_cell(dims[key]))}</td>'
                        for key in ('stability', 'capability', 'catalog'))
        body.append(
            f'<tr><td><strong>{esc(row["name"])}</strong><div class="sub">'
            f'{esc(row.get("base_url") or "")}</div></td>'
            f'<td>{esc(row.get("model") or "")}</td>'
            f'<td>{esc(row.get("mode") or "")}</td>'
            f'<td><span class="badge {badge_level(row["protocol"])}">'
            f'{esc(row["protocol"] or "")}</span></td>'
            f'<td><span class="badge {badge_level(row["usability"]["grade"].lower())}">'
            f'{esc(row["usability"]["grade"])}'
            f' ({row["usability"]["coverage"]}%)</span></td>'
            f'{cells}'
            f'<td>{len(row["hard_fails"])}</td></tr>')
    social = meta_tags(
        '中转查 · 中转对比',
        '多家 OpenAI 兼容中转的协议面、可用性与硬伤对比，全部为脱敏示例。',
        f'{SITE_URL}/demo/compare.html',
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中转查 · 中转对比</title>
{social}
<style>
:root {{ --bg:#f6f7f9; --panel:#fff; --ink:#1f2328; --muted:#667085; --line:#e4e7ec;
         --pass:#137a4b; --warn:#a15c00; --fail:#b42318; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
        font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:28px; margin:0 0 6px; }}
.meta {{ color:var(--muted); font-size:14px; }}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:20px 0 24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
.label {{ color:var(--muted); font-size:13px; }}
.value {{ font-size:24px; font-weight:650; }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th, td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); background:#fafbfc; font-weight:600; }}
tr:last-child td {{ border-bottom:0; }}
.sub {{ color:var(--muted); font-size:12px; }}
.badge {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; }}
.badge.pass {{ background:#e7f6ee; color:var(--pass); }}
.badge.warn {{ background:#fff4e5; color:var(--warn); }}
.badge.fail {{ background:#fee4e2; color:var(--fail); }}
.badge.na {{ background:#eef0f3; color:var(--muted); }}
.note {{ color:var(--muted); font-size:13px; margin-top:12px; }}
.lede {{ font-size:15px; margin:12px 0 0; max-width:900px; }}
.wrap-list {{ margin:0; padding-left:20px; }}
.wrap-list li {{ margin:6px 0; }}
footer {{ color:var(--muted); font-size:12px; margin-top:20px; }}
footer a {{ color:#1f5fbf; text-decoration:none; }}
@media (max-width:720px) {{ .cards {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; }} section {{ break-inside:avoid; }} }}
</style></head><body><div class="wrap">
<h1>中转查 · 中转对比</h1>
<div class="meta">生成：{esc(stamp())}；目标数：{total}</div>
<p class="lede">把多份审计快照放到同一口径下比较。主分只看可用性；协议契约与错误码请回单份报告复核。</p>
<div class="cards">
  <div class="card"><div class="label">可用性 A</div><div class="value">{usable_a}/{total}</div></div>
  <div class="card"><div class="label">协议面 inconsistent</div><div class="value">{protocol_bad}/{total}</div></div>
  <div class="card"><div class="label">平均可用性覆盖度</div><div class="value">{round(sum(row["usability"]["coverage"] for row in rows)/total)}%</div></div>
</div>
<section>
<table><thead><tr><th>目标</th><th>型号</th><th>模式</th><th>协议面</th><th>可用性</th>
<th>稳定性</th><th>能力</th><th>目录</th><th>硬伤</th></tr></thead><tbody>
{''.join(body)}
</tbody></table>
<p class="note">可用性主分只看稳定性/能力/目录；协议契约与错误码在单份报告附录，不计入主分。
硬伤数来自协议 findings（cap、续接、非法参数、错误码、Responses/Chat 面等）。</p>
</section>
{_wrapper_section(rows)}
<footer>低分不等于型号假；同门型号替换不在覆盖范围内。差异请回到单份报告的证据目录复核。 · <a href="https://zhongzhuancha.com/">中转查</a></footer>
</div></body></html>
'''


def run(args):
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    rows = build_rows(load_specs(args))
    args.out.mkdir(parents=True, mode=0o700)
    save(args.out / 'COMPARE.json', {'schema': SCHEMA, 'created_asia': stamp(),
                                    'targets': rows})
    (args.out / 'COMPARE.html').write_text(render_html(rows), encoding='utf-8')
    write_manifest(args.out)
    print(json.dumps({'status': 'complete', 'targets': len(rows),
                      'report': str((args.out / 'COMPARE.html').resolve()),
                      'identity_authenticated': False}, ensure_ascii=False))
    return 0


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

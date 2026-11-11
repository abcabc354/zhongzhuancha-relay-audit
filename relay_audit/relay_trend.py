"""Historical trend page for repeated audits of the same relay."""
import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from . import protocol_scorecard
from .evidence import ContractError, read_json, save, stamp, write_manifest
from .html_meta import SITE_URL, meta_tags
from .relay_compare import HARD

SCHEMA = 'relay-trend-v1'


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    return parser


def load_config(path):
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ContractError('invalid trend config') from error
    series = doc.get('series') if isinstance(doc, dict) else None
    if not isinstance(series, list) or not series:
        raise ContractError('config needs a non-empty series list')
    loaded = []
    for item in series:
        if not isinstance(item, dict) or not item.get('name'):
            raise ContractError('each series needs name')
        audits = item.get('audits')
        if not isinstance(audits, list) or not audits:
            raise ContractError('each series needs audits')
        loaded.append({'name': item['name'], 'audits': [Path(p) for p in audits]})
    return loaded


def _sort_key(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        parsed = datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_point(path):
    root = Path(path)
    plan = read_json(root / 'PLAN.json')
    summary = read_json(root / 'SUMMARY.json')
    verdict = summary.get('verdict') or {}
    results = summary.get('results') or {}
    meta = results.get('_meta') or {}
    findings = verdict.get('findings') or []
    card = protocol_scorecard.build({'targets': [{
        'name': root.name, 'model': plan.get('model'),
        'status': verdict.get('status'), 'findings': findings}]})
    target = card['targets'][0]
    min_summary = (results.get('responses_min') or {}).get('summary') or {}
    return {
        'started': meta.get('started_asia') or '',
        'mode': meta.get('mode'),
        'protocol': verdict.get('status'),
        'usability': target['overall'],
        'dimensions': target['dimensions'],
        'hard_fails': [item['code'] for item in findings
                       if item.get('level') == 'fail' and item.get('code') in HARD],
        'warns': sum(item.get('level') == 'warn' for item in findings),
        'instructions_len': min_summary.get('instructions_len'),
        'instructions_sha256': min_summary.get('instructions_sha256'),
        'source': str(root.resolve()),
    }


def _changes(points):
    changes = []
    for previous, current in zip(points, points[1:]):
        at = (current.get('started') or '')[11:16]
        if previous.get('protocol') != current.get('protocol'):
            changes.append(f"{at} 协议面 {previous.get('protocol')} → {current.get('protocol')}")
        old, new = previous.get('usability') or {}, current.get('usability') or {}
        if (old.get('grade'), old.get('coverage')) != (new.get('grade'), new.get('coverage')):
            changes.append(f"{at} 可用性 {old.get('grade')} ({old.get('coverage')}%) → "
                           f"{new.get('grade')} ({new.get('coverage')}%)")
        if previous.get('instructions_sha256') != current.get('instructions_sha256'):
            old_sha = (previous.get('instructions_sha256') or '-')[:8]
            new_sha = (current.get('instructions_sha256') or '-')[:8]
            changes.append(f"{at} 包装哈希 {old_sha} → {new_sha}")
        if previous.get('mode') != current.get('mode'):
            changes.append(f"{at} 模式 {previous.get('mode')} → {current.get('mode')}")
    return changes


def build_series(spec):
    points = sorted((load_point(path) for path in spec['audits']),
                    key=lambda item: _sort_key(item['started']))
    if not points:
        raise ContractError('series has no points')
    return {'name': spec['name'], 'model': None, 'points': points,
            'changes': _changes(points), 'latest': points[-1]}


def _chart(points):
    width, height = 920, 180
    left, right, top, bottom = 44, 18, 18, 30
    count = len(points)

    def x(index):
        if count == 1:
            return left + (width - left - right) / 2
        return left + (width - left - right) * index / (count - 1)

    def y(value):
        return top + (height - top - bottom) * (1 - (value or 0) / 100)

    grid = []
    for value in (0, 50, 100):
        gy = y(value)
        grid.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" '
                    f'stroke="#e4e7ec" stroke-width="1"/>')
        grid.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end" '
                    f'font-size="11" fill="#667085">{value}</text>')
    coords = ' '.join(f'{x(i):.1f},{y(point["usability"]["coverage"]):.1f}'
                      for i, point in enumerate(points))
    dots = []
    labels = []
    colors = {'consistent': '#137a4b', 'partial': '#a15c00', 'inconsistent': '#b42318'}
    for i, point in enumerate(points):
        px, py = x(i), y(point['usability']['coverage'])
        dots.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" '
                    f'fill="{colors.get(point.get("protocol"), "#667085")}" '
                    f'stroke="#fff" stroke-width="2"/>')
        labels.append(f'<text x="{px:.1f}" y="{height - 8}" text-anchor="middle" '
                      f'font-size="11" fill="#667085">{html.escape((point.get("started") or "")[11:16])}</text>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'role="img" aria-label="usability coverage trend">'
            + ''.join(grid)
            + f'<polyline points="{coords}" fill="none" stroke="#1f5fbf" stroke-width="2.5"/>'
            + ''.join(dots) + ''.join(labels) + '</svg>')


def render_html(series):
    esc = html.escape
    total_points = sum(len(item['points']) for item in series)
    latest_a = sum(item['latest']['usability']['grade'] == 'A' for item in series)
    sections = []
    for item in series:
        latest = item['latest']
        rows = []
        for point in item['points']:
            wrapper = '-'
            if point.get('instructions_len') is not None:
                sha = (point.get('instructions_sha256') or '')[:8]
                wrapper = f"{point['instructions_len']} / {sha}"
            rows.append(
                f'<tr><td>{esc((point.get("started") or "")[5:16])}</td>'
                f'<td>{esc(point.get("mode") or "")}</td>'
                f'<td><span class="badge {esc(point.get("protocol") or "na")}">'
                f'{esc(point.get("protocol") or "")}</span></td>'
                f'<td>{esc(point["usability"]["grade"])}'
                f' ({point["usability"]["coverage"]}%)</td>'
                f'<td>{len(point.get("hard_fails") or [])}</td>'
                f'<td>{point.get("warns")}</td><td><code>{esc(wrapper)}</code></td></tr>')
        changes = item.get('changes') or ['窗口内无变化']
        sections.append(f'''
<section>
  <h2>{esc(item["name"])}
    <span class="badge {esc(latest.get("protocol") or "na")}">{esc(latest.get("protocol") or "")}</span>
    <span class="badge grade">{esc(latest["usability"]["grade"])} ({latest["usability"]["coverage"]}%)</span>
  </h2>
  {_chart(item["points"])}
  <table><thead><tr><th>时间</th><th>模式</th><th>协议面</th><th>可用性</th>
  <th>硬伤</th><th>警告</th><th>包装（字符/hash）</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  <h3>变化</h3><ul>{''.join(f"<li>{esc(text)}</li>" for text in changes)}</ul>
</section>''')
    social = meta_tags(
        '中转查 · 历史趋势',
        '同一中转多次审计的可用性、协议面与包装变化趋势，全部为脱敏示例。',
        f'{SITE_URL}/demo/trend.html',
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中转查 · 历史趋势</title>
{social}
<style>
:root {{ --bg:#f6f7f9; --panel:#fff; --ink:#1f2328; --muted:#667085; --line:#e4e7ec;
         --pass:#137a4b; --warn:#a15c00; --fail:#b42318; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
        font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:28px; margin:0 0 6px; }}
.meta {{ color:var(--muted); font-size:14px; }}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:20px 0 24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
.label {{ color:var(--muted); font-size:13px; }}
.value {{ font-size:24px; font-weight:650; }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
           padding:20px; margin-bottom:18px; }}
h2 {{ font-size:18px; margin:0 0 12px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
h3 {{ font-size:15px; margin:18px 0 8px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; margin-top:6px; }}
th, td {{ text-align:left; padding:8px 9px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); background:#fafbfc; font-weight:600; }}
tr:last-child td {{ border-bottom:0; }}
.badge {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; }}
.badge.consistent {{ background:#e7f6ee; color:var(--pass); }}
.badge.partial {{ background:#fff4e5; color:var(--warn); }}
.badge.inconsistent {{ background:#fee4e2; color:var(--fail); }}
.badge.grade {{ background:#eef0f3; color:var(--ink); }}
.badge.na {{ background:#eef0f3; color:var(--muted); }}
code {{ background:#f2f4f7; border-radius:5px; padding:1px 5px; font-size:12px; }}
ul {{ margin:6px 0 0; padding-left:20px; }}
footer {{ color:var(--muted); font-size:12px; margin-top:20px; }}
footer a {{ color:#1f5fbf; text-decoration:none; }}
@media (max-width:720px) {{ .cards {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; }} section {{ break-inside:avoid; }} }}
</style></head><body><div class="wrap">
<h1>中转查 · 历史趋势</h1>
<div class="meta">生成：{esc(stamp())}；系列：{len(series)}；数据点：{total_points}</div>
<p class="lede">每个系列是同一目标的历史快照。折线表示可用性覆盖度，点的颜色表示协议面；变化列表只记录状态切换。</p>
<div class="cards">
  <div class="card"><div class="label">系列数</div><div class="value">{len(series)}</div></div>
  <div class="card"><div class="label">最新可用性 A</div><div class="value">{latest_a}/{len(series)}</div></div>
  <div class="card"><div class="label">数据点</div><div class="value">{total_points}</div></div>
</div>
{''.join(sections)}
<footer>趋势只反映审计快照；低分不等于型号假，同门型号替换不在覆盖范围内。 · <a href="https://zhongzhuancha.com/">中转查</a></footer>
</div></body></html>
'''


def run(args):
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    series = [build_series(spec) for spec in load_config(args.config)]
    args.out.mkdir(parents=True, mode=0o700)
    save(args.out / 'TREND.json', {'schema': SCHEMA, 'created_asia': stamp(),
                                   'series': series})
    (args.out / 'TREND.html').write_text(render_html(series), encoding='utf-8')
    write_manifest(args.out)
    print(json.dumps({'status': 'complete', 'series': len(series),
                      'points': sum(len(item['points']) for item in series),
                      'report': str((args.out / 'TREND.html').resolve()),
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

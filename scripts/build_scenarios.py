#!/usr/bin/env python3
"""Render sanitized scenario fixtures into static demo pages.

Fixtures are committed under examples/scenarios/<slug>/. The generated
docs/demo/scenarios/ tree is not committed; CI and Pages rebuild it.
"""
import contextlib
import io
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from relay_audit import relay_audit  # noqa: E402

DEST = ROOT / 'docs' / 'demo' / 'scenarios'
FIXTURES = ROOT / 'examples' / 'scenarios'
SCENARIOS = [
    ('responses-good', '正常 Responses', '主分 A，协议面 consistent。'),
    ('chat-only', 'Chat-only 自动回退', 'mode=chat，对话维度 n/a。'),
    ('wrapper-shell', 'Responses 壳', '主分 A，附录包装 warn。'),
    ('cap-ignored', 'cap 被忽略', '主分 A，output.cap fail。'),
    ('prev-unsupported', '续接不支持', '主分 A，previous.roundtrip fail。'),
    ('usage-drift', '同请求用量漂移', '稳定性 warn，总分约 92。'),
]

INDEX = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中转查 · relay-audit · 场景库</title>
<style>
:root{{--bg:#f5f7fa;--panel:#fff;--ink:#1f2328;--muted:#667085;--line:#e4e7ec;--blue:#1f5fbf}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:40px 24px 64px}}
.eyebrow{{font-size:12px;letter-spacing:.24em;color:var(--blue);font-weight:650}}
h1{{font-size:34px;margin:10px 0 8px;letter-spacing:-.02em}}
.lede{{color:var(--muted);max-width:800px;margin:0 0 26px}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.card{{display:block;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;text-decoration:none;color:var(--ink)}}
.card h2{{font-size:18px;margin:0 0 6px}}.card p{{margin:0;color:var(--muted);font-size:14px}}
.card .tag{{font-size:12px;color:var(--blue);font-weight:650;letter-spacing:.08em;margin-bottom:8px}}
.note{{margin-top:22px;color:var(--muted);font-size:13px}}
a{{color:var(--blue)}}@media(max-width:720px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">SCENARIO FIXTURES</div>
<h1>场景库</h1>
<p class="lede">全部为脱敏 fixture，不是实时中转数据；用于说明报告在不同协议面下怎么读。</p>
<div class="grid">
{cards}
</div>
<p class="note">返回 <a href="../">Demo 首页</a> · <a href="https://github.com/abcabc354/zhongzhuancha-relay-audit/tree/main/docs/scenarios">场景文档</a></p>
</div></body></html>
'''


def build():
    if not FIXTURES.is_dir():
        raise SystemExit('missing examples/scenarios')
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    cards = []
    for slug, title, expected in SCENARIOS:
        src = FIXTURES / slug
        if not (src / 'SUMMARY.json').exists():
            raise SystemExit(f'missing fixture: {src}')
        out = DEST / slug
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = relay_audit.main(['--from-audit', str(src), '--name', slug,
                                     '--out', str(out)])
        if code not in (0, 2):
            raise SystemExit(f'{slug}: relay_audit exited {code}')
        report = out / 'REPORT.html'
        text = report.read_text(encoding='utf-8')
        text = text.replace(str(src.resolve()), f'examples/scenarios/{slug}')
        report.write_text(text, encoding='utf-8')
        for extra in out.iterdir():
            if extra.name != 'REPORT.html':
                extra.unlink()
        cards.append(
            f'<a class="card" href="{slug}/REPORT.html">'
            f'<div class="tag">SCENARIO</div><h2>{title}</h2>'
            f'<p><code>{slug}</code> · {expected}</p></a>')
    (DEST / 'index.html').write_text(INDEX.format(cards='\n'.join(cards)), encoding='utf-8')
    print(f'built {len(SCENARIOS)} scenarios in {DEST}')


if __name__ == '__main__':
    build()

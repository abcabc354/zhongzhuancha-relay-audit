"""Usability scorecard for relay audits.

Main score answers "can I use it": stability, dialogue, capability, catalog.
Protocol contract and error-shape findings are kept in an appendix and are
not part of the usability score. Not authenticity probability.
"""
import argparse
import json
from pathlib import Path

from .evidence import (ContractError, read_json, save, stamp, write_manifest)

SCHEMA = 'gpt-protocol-scorecard-v4'
LEVELS = {'pass': 2, 'warn': 1, 'fail': 0}
MAIN = {
    'stability': {
        'label': '稳定性',
        'codes': ('responses.surface', 'chat.surface', 'chat.stream', 'usage.stability'),
    },
    'dialogue': {
        'label': '对话',
        'codes': ('responses.attribution', 'responses.final_answer',
                  'cache.retention', 'text.verbosity'),
    },
    'capability': {
        'label': '能力',
        'codes': ('image.vision', 'tools.function_call', 'structured.output',
                  'reasoning.scaling', 'chat.tools', 'chat.structured', 'chat.vision'),
    },
    'catalog': {
        'label': '目录',
        'codes': ('catalog.liveness',),
    },
}
APPENDIX = {
    'wrapper': {
        'label': '包装',
        'codes': ('wrapper.instructions', 'wrapper.persona', 'wrapper.shared'),
    },
    'contract': {
        'label': '协议契约',
        'codes': ('output.cap', 'previous.roundtrip', 'invalid.parameter',
                  'store.echo'),
    },
    'error_shapes': {
        'label': '错误码',
        'codes': ('error.invalid_model', 'error.invalid_cap', 'error.unauthorized'),
    },
}


def grade(score):
    if score is None:
        return 'n/a'
    if score >= 90:
        return 'A'
    if score >= 70:
        return 'B'
    if score >= 50:
        return 'C'
    return 'D'


def score_dimension(findings, codes):
    by_code = {item['code']: item for item in findings if item.get('code') in codes}
    counted = [item for item in by_code.values() if item.get('level') in LEVELS]
    info = [item for item in by_code.values() if item.get('level') == 'info']
    items = []
    for code in codes:
        item = by_code.get(code)
        if item:
            items.append({'code': code, 'level': item.get('level'),
                          'message': item.get('message'),
                          'evidence': item.get('evidence')})
    if not counted:
        return {'status': 'n/a', 'coverage': None, 'pass': 0, 'warn': 0, 'fail': 0,
                'info': len(info), 'sample': '0/0', 'items': items}
    levels = [item['level'] for item in counted]
    status = 'fail' if 'fail' in levels else ('warn' if 'warn' in levels else 'pass')
    passed = sum(level == 'pass' for level in levels)
    coverage = round(100 * passed / len(levels))
    sample = f"{passed}/{len(levels)}"
    for item in counted:
        if item['code'] != 'catalog.liveness':
            continue
        evidence = item.get('evidence') or {}
        checked = evidence.get('checked') or {}
        failed = evidence.get('failed') or {}
        if checked:
            live = len(checked) - len(failed)
            coverage = round(100 * live / len(checked))
            sample = f"{live}/{len(checked)}"
            status = 'pass' if coverage == 100 else ('fail' if coverage == 0 else 'warn')
    return {'status': status, 'coverage': coverage, 'sample': sample,
            'pass': passed, 'warn': sum(level == 'warn' for level in levels),
            'fail': sum(level == 'fail' for level in levels), 'info': len(info),
            'items': items}


def overall_grade(dimensions):
    coverages = [value['coverage'] for value in dimensions.values()
                 if value['coverage'] is not None]
    if not coverages:
        return {'grade': 'n/a', 'coverage': None}
    coverage = round(sum(coverages) / len(coverages))
    return {'grade': grade(coverage), 'coverage': coverage}


def build_target(target):
    findings = target.get('findings') or []
    if not isinstance(findings, list) or not findings:
        raise ContractError('target has no findings')
    dimensions = {key: score_dimension(findings, spec['codes'])
                  for key, spec in MAIN.items()}
    appendix = {key: score_dimension(findings, spec['codes'])
                for key, spec in APPENDIX.items()}
    return {'name': target.get('name') or 'target', 'model': target.get('model'),
            'status': target.get('status'), 'overall': overall_grade(dimensions),
            'dimensions': dimensions, 'appendix': appendix}


def build(batch):
    targets = batch.get('targets') if isinstance(batch, dict) else None
    if not isinstance(targets, list) or not targets:
        raise ContractError('batch summary has no targets')
    return {'schema': SCHEMA, 'created_asia': stamp(),
            'dimensions': [{'key': key, 'label': spec['label']}
                           for key, spec in MAIN.items()],
            'appendix': [{'key': key, 'label': spec['label']}
                         for key, spec in APPENDIX.items()],
            'targets': [build_target(target) for target in targets],
            'meaning': 'usability_score_not_authenticity_probability',
            'identity_authenticated': False}


def load_batch(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ContractError('invalid batch summary') from error


def load_audit(path):
    root = Path(path)
    summary = read_json(root / 'SUMMARY.json')
    verdict = summary.get('verdict') or {}
    plan = read_json(root / 'PLAN.json') if (root / 'PLAN.json').exists() else {}
    return {'name': plan.get('base_url') or root.name, 'model': plan.get('model'),
            'status': verdict.get('status'), 'findings': verdict.get('findings') or []}


def _cell(value):
    if value['status'] == 'n/a':
        return 'n/a'
    sample = value.get('sample')
    suffix = f" ({sample})" if sample else ''
    return f"{value['status']} {value['coverage']}%{suffix}"


def render(scorecard):
    labels = [item['label'] for item in scorecard['dimensions']]
    app_labels = [item['label'] for item in scorecard['appendix']]
    lines = ['# 中转查 · 中转可用性记分卡（v4）', '',
             f"时间：{scorecard['created_asia']}", '',
             '> 主分只看**能不能用**：稳定性、对话、能力、目录。',
             '> 协议契约与错误码在附录，**不计入**主分；分数不是真伪概率。',
             '> 主分：覆盖度 A≥90 / B≥70 / C≥50 / D<50。', '',
             '| 目标 | 型号 | ' + ' | '.join(labels) + ' | 总分 |',
             '|---|---|' + '---|' * len(labels) + '---|']
    for target in scorecard['targets']:
        cells = [_cell(target['dimensions'][spec['key']]) for spec in scorecard['dimensions']]
        overall = target['overall']
        lines.append(f"| {target['name']} | `{target.get('model')}` | "
                     + ' | '.join(cells)
                     + f" | {overall['grade']}"
                     + (f" ({overall['coverage']}%)" if overall['coverage'] is not None else '')
                     + ' |')
    lines += ['', '## 附录：协议细节（不计入主分）', '',
              '| 目标 | ' + ' | '.join(app_labels) + ' |', '|---|' + '---|' * len(app_labels)]
    for target in scorecard['targets']:
        cells = [_cell(target['appendix'][spec['key']]) for spec in scorecard['appendix']]
        lines.append(f"| {target['name']} | " + ' | '.join(cells) + ' |')
    lines += ['', '## 维度说明', '',
              '- 稳定性：Responses/Chat 面可用、同一请求用量稳定。',
              '- 对话：attribution、final_answer、cache、verbosity。',
              '- 能力：视觉、工具调用、结构化输出、reasoning 缩放。',
              '- 目录：`/models` 抽检型号的存活比例。',
              '- 包装（附录）：instructions、persona、跨型号一致性。',
              '- 协议契约（附录）：cap、续接、非法 effort、store。',
              '- 错误码（附录）：非法 model / 无效 cap / 无凭据的错误形状。',
              '', '## 明细', '']
    for target in scorecard['targets']:
        overall = target['overall']
        lines += [f"### {target['name']}（{target.get('model')}）", '',
                  f"可用性：**{overall['grade']}**；覆盖度 {overall['coverage']}%。", '',
                  '| 维度 | 状态 | 覆盖度 | pass/warn/fail | 关键项 |',
                  '|---|---|---:|---|---|']
        for spec in scorecard['dimensions']:
            value = target['dimensions'][spec['key']]
            key_items = [f"{item['code']}={item['level']}" for item in value['items']
                         if item['level'] in ('fail', 'warn')][:4]
            lines.append(f"| {spec['label']} | {value['status']} | "
                         f"{value['coverage'] if value['coverage'] is not None else 'n/a'} | "
                         f"{value['pass']}/{value['warn']}/{value['fail']} | "
                         f"{', '.join(key_items) or '-'} |")
        lines += ['', '协议细节：']
        for spec in scorecard['appendix']:
            value = target['appendix'][spec['key']]
            key_items = [f"{item['code']}={item['level']}" for item in value['items']
                         if item['level'] in ('fail', 'warn')][:4]
            lines.append(f"- {spec['label']}：{value['status']} "
                         f"({value['pass']}/{value['pass'] + value['warn'] + value['fail']})"
                         + (f"；{', '.join(key_items)}" if key_items else ''))
        lines.append('')
    lines += ['## 边界', '',
              '- 主分只回答“能不能用”，不回答“协议是否忠实”或“型号真假”。',
              '- 协议契约/错误码在附录，供工程排查；不计入主分。',
              '- 同门型号替换不在覆盖范围内。', '']
    return '\n'.join(lines)


def run(args):
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    if args.batch:
        scorecard = build(load_batch(args.batch))
    elif args.audit:
        scorecard = build({'targets': [load_audit(path) for path in args.audit]})
    else:
        raise ContractError('--batch or --audit is required')
    args.out.mkdir(parents=True, mode=0o700)
    save(args.out / 'SCORECARD.json', scorecard)
    (args.out / 'SCORECARD.md').write_text(render(scorecard), encoding='utf-8')
    write_manifest(args.out)
    print(json.dumps({'status': 'complete', 'targets': len(scorecard['targets']),
                      'evidence': str(args.out.resolve()),
                      'identity_authenticated': False}, ensure_ascii=False))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path)
    parser.add_argument('--audit', type=Path, action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    return parser


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

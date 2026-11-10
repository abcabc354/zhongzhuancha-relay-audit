"""Batch runner for GPT protocol-surface audits."""
import argparse
import json
import re
from pathlib import Path

from . import protocol_audit
from .evidence import ContractError, read_json, save, stamp, write_manifest

SCHEMA = 'gpt-protocol-audit-batch-v1'
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-local', action='store_true')
    parser.add_argument('--enable-remote', action='store_true')
    return parser


def load_targets(path):
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ContractError('invalid batch config') from error
    targets = doc.get('targets') if isinstance(doc, dict) else None
    if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
        raise ContractError('targets must be a list of 1..10')
    loaded = []
    seen = set()
    for item in targets:
        if not isinstance(item, dict):
            raise ContractError('each target must be an object')
        name = item.get('name')
        base = item.get('base_url')
        model = item.get('model')
        if not all(isinstance(value, str) and value.strip() for value in (name, base, model)):
            raise ContractError('target requires name, base_url and model')
        if not NAME.fullmatch(name):
            raise ContractError('target name must be a simple slug')
        if name in seen:
            raise ContractError('duplicate target name')
        seen.add(name)
        exclude = item.get('exclude_models') or []
        if not isinstance(exclude, list) or any(not isinstance(x, str) for x in exclude):
            raise ContractError('exclude_models must be a list of strings')
        catalog_mode = item.get('catalog_mode') or 'target'
        if catalog_mode not in ('target', 'sample'):
            raise ContractError('catalog_mode must be target or sample')
        mode = item.get('mode') or 'auto'
        if mode not in ('auto', 'responses', 'chat'):
            raise ContractError('mode must be auto, responses or chat')
        loaded.append({'name': name, 'base_url': base.strip(), 'model': model.strip(),
                       'api_key_file': item.get('api_key_file'),
                       'api_key_env': item.get('api_key_env'),
                       'exclude_models': exclude, 'catalog_mode': catalog_mode, 'mode': mode})
    return loaded


def render(summary):
    lines = ['# GPT 中转协议面审计：批量对比', '',
             f"时间：{summary['started_asia']}", '',
             '| 目标 | 型号 | 协议面 | pass/warn/fail | cap | prev | tools | structured | err.model | err.cap | err.auth |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for target in summary['targets']:
        findings = {item['code']: item['level'] for item in target.get('findings') or []}
        counts = target.get('counts') or {}
        lines.append(
            f"| {target['name']} | `{target['model']}` | {target.get('status', 'error')} | "
            f"{counts.get('pass', '-')}/{counts.get('warn', '-')}/{counts.get('fail', '-')} | "
            f"{findings.get('output.cap', '-')} | "
            f"{findings.get('previous.roundtrip', '-')} | "
            f"{findings.get('tools.function_call', '-')} | "
            f"{findings.get('structured.output', '-')} | "
            f"{findings.get('error.invalid_model', '-')} | "
            f"{findings.get('error.invalid_cap', '-')} | "
            f"{findings.get('error.unauthorized', '-')} |")
    lines += ['', '## 说明', '',
              '- 每行是一个 `base_url + model` 组合；同一中转的不同型号也会分开跑。',
              '- `cap / prev / tools / structured` 是四个关键契约检查的级别。',
              '- 协议面 `inconsistent` 不等于型号假；只说明协议契约不完整。',
              '- 批量报告不能替代单个目标的证据目录；每个目标仍有独立 `REPORT.md`。', '']
    return '\n'.join(lines)


def run(args):
    targets = load_targets(args.config)
    if not args.enable_remote:
        print(json.dumps({'status': 'dry_run', 'targets': targets,
                          'requests_per_target': 25, 'total_requests': 25 * len(targets)},
                         ensure_ascii=False))
        return 0
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    args.out.mkdir(parents=True, mode=0o700)
    summary = {'schema': SCHEMA, 'started_asia': stamp(), 'targets': []}
    for target in targets:
        sub = args.out / target['name']
        key_file = Path(target['api_key_file']) if target.get('api_key_file') else None
        namespace = argparse.Namespace(out=sub, base_url=target['base_url'], model=target['model'],
                                       api_key_file=key_file, api_key_env=target.get('api_key_env'),
                                       allow_local=args.allow_local, enable_remote=True,
                                       verify=None, exclude_model=target.get('exclude_models') or [],
                                       catalog_mode=target.get('catalog_mode') or 'target',
                                       mode=target.get('mode') or 'auto')
        try:
            code = protocol_audit.run(namespace)
            stored = read_json(sub / 'SUMMARY.json')
        except Exception as error:  # noqa: BLE001
            summary['targets'].append({'name': target['name'], 'model': target['model'],
                                       'status': 'error',
                                       'error': type(error).__name__ + ': ' + str(error)[:300],
                                       'counts': {}})
            continue
        verdict = stored['verdict']
        summary['targets'].append({'name': target['name'], 'model': target['model'],
                                   'exit': code, 'status': verdict['status'],
                                   'counts': verdict['counts'], 'findings': verdict['findings'],
                                   'report': str((sub / 'REPORT.md').resolve())})
    save(args.out / 'BATCH-SUMMARY.json', summary)
    (args.out / 'BATCH-REPORT.md').write_text(render(summary), encoding='utf-8')
    write_manifest(args.out)
    print(json.dumps({'status': 'complete', 'targets': len(summary['targets']),
                      'inconsistent': sum(item.get('status') == 'inconsistent'
                                          for item in summary['targets']),
                      'evidence': str(args.out.resolve())}, ensure_ascii=False))
    return 2 if any(item.get('status') == 'inconsistent' for item in summary['targets']) else 0


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

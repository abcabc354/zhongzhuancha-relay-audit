"""Daily relay inspection: audit fixed targets, then refresh compare/trend pages."""
import argparse
import contextlib
import io
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import relay_audit, relay_compare, relay_trend
from .evidence import (ContractError, read_json, save, stamp, write_manifest)

ROOT = Path(os.environ.get('RELAY_AUDIT_PROJECT') or Path.cwd()).resolve()
SCHEMA = 'relay-inspect-run-v1'


def load_targets(path):
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ContractError('invalid targets file') from error
    items = doc.get('targets') if isinstance(doc, dict) else None
    if not isinstance(items, list) or not items:
        raise ContractError('targets file needs a non-empty targets list')
    targets = []
    for item in items:
        if not isinstance(item, dict) or not item.get('name') or not item.get('base_url'):
            raise ContractError('each target needs name and base_url')
        if not item.get('api_key_file'):
            raise ContractError('each target needs api_key_file')
        targets.append({'name': item['name'], 'base_url': item['base_url'],
                        'model': item.get('model') or 'gpt-6.1-sol',
                        'api_key_file': item['api_key_file']})
    return targets


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-root', type=Path,
                        default=ROOT / '_evidence' / 'relay-inspect')
    parser.add_argument('--targets', type=Path,
                        default=ROOT / 'config' / 'inspect-targets.json')
    parser.add_argument('--date',
                        default=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d'))
    parser.add_argument('--only',
                        help='comma separated target names; default all')
    parser.add_argument('--mode', choices=('auto', 'responses', 'chat'), default='auto')
    parser.add_argument('--dry-run', action='store_true')
    return parser


def _selected(targets, only):
    if not only:
        return targets
    names = {item.strip() for item in only.split(',') if item.strip()}
    selected = [target for target in targets if target['name'] in names]
    if not selected:
        raise ContractError('no matching targets')
    return selected


def _run_audit(target, day_dir, mode):
    out = day_dir / target['name']
    if out.exists():
        return {'name': target['name'], 'status': 'skipped_exists',
                'audit': str(out / 'AUDIT')}
    argv = ['--name', target['name'], '--out', str(out),
            '--base-url', target['base_url'], '--model', target['model'],
            '--api-key-file', str(ROOT / target['api_key_file']),
            '--enable-remote', '--mode', mode]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = relay_audit.main(argv)
    summary_path = out / 'AUDIT' / 'SUMMARY.json'
    status = None
    if summary_path.exists():
        try:
            status = read_json(summary_path).get('verdict', {}).get('status')
        except ContractError:
            status = None
    return {'name': target['name'], 'exit': code, 'status': status,
            'audit': str((out / 'AUDIT').resolve()),
            'report': str((out / 'REPORT.html').resolve())}


def _run_compare(day_dir, results):
    audits = [item for item in results
              if item.get('audit') and Path(item['audit']).exists()]
    if not audits:
        return None
    config = {'targets': [{'name': item['name'], 'audit': item['audit']}
                          for item in audits]}
    config_path = day_dir / 'COMPARE-CONFIG.json'
    save(config_path, config)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        relay_compare.main(['--config', str(config_path),
                            '--out', str(day_dir / 'COMPARE')])
    return str((day_dir / 'COMPARE' / 'COMPARE.html').resolve())


def _run_trend(out_root, day_dir, selected):
    series = []
    for target in selected:
        audits = sorted(out_root.glob(f'*/{target["name"]}/AUDIT'))
        if audits:
            series.append({'name': target['name'],
                           'audits': [str(path) for path in audits]})
    if not series:
        return None
    config_path = day_dir / 'TREND-CONFIG.json'
    save(config_path, {'series': series})
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        relay_trend.main(['--config', str(config_path),
                          '--out', str(day_dir / 'TREND')])
    return str((day_dir / 'TREND' / 'TREND.html').resolve())


def run(args):
    targets = load_targets(args.targets)
    selected = _selected(targets, args.only)
    if args.dry_run:
        print(json.dumps({'status': 'dry_run', 'date': args.date,
                          'targets': [target['name'] for target in selected],
                          'requests_per_target_estimate': 25}, ensure_ascii=False))
        return 0
    out_root = Path(args.out_root)
    day_dir = out_root / args.date
    if day_dir.exists() and any(day_dir.iterdir()):
        raise ContractError('day directory already has data; refusing to overwrite')
    day_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    started = stamp()
    results = []
    for target in selected:
        try:
            results.append(_run_audit(target, day_dir, args.mode))
        except Exception as error:  # noqa: BLE001
            results.append({'name': target['name'], 'status': 'error',
                            'error': type(error).__name__ + ': ' + str(error)[:300]})
    compare = _run_compare(day_dir, results)
    trend = _run_trend(out_root, day_dir, selected)
    log = {'schema': SCHEMA, 'date': args.date, 'started_asia': started,
           'finished_asia': stamp(), 'mode': args.mode,
           'targets': results, 'compare': compare, 'trend': trend}
    save(day_dir / 'RUN-LOG.json', log)
    write_manifest(day_dir)
    failures = [item['name'] for item in results if item.get('status') == 'error']
    print(json.dumps({'status': 'complete' if not failures else 'partial',
                      'date': args.date, 'targets': len(results),
                      'failures': failures, 'compare': compare,
                      'trend': trend}, ensure_ascii=False))
    return 0 if not failures else 2


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

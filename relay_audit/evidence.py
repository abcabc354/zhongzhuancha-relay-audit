"""Strict JSON, bounded local bundles and tamper-evident receipts."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo


MAX_JSON = 32 * 1024 * 1024


def _clean(value, secret):
    if isinstance(value, str):
        value = value.replace(secret, '[REDACTED]') if secret else value
        value = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [REDACTED]', value)
        return re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', value)
    if isinstance(value, dict):
        return {_clean(str(key), secret):
                ('[REDACTED]' if str(key).lower() in ('authorization', 'x-api-key', 'key', 'api_key')
                 else _clean(item, secret))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item, secret) for item in value]
    return value


def _checkpoint(path, data):
    target = Path(path)
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(',', ':')).encode('utf-8') + b'\n'
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix='.' + target.name + '.',
                                                suffix='.tmp', dir=target.parent)
        with os.fdopen(descriptor, 'wb') as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        directory = os.open(target.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


class ContractError(ValueError):
    pass


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode()


def object_hash(value):
    return digest(canonical(value))


def stamp():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='milliseconds')


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ContractError('duplicate JSON field')
        out[key] = value
    return out


def loads(raw):
    def reject(_):
        raise ContractError('nonfinite JSON number')
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)
    except (ValueError, UnicodeError) as error:
        raise ContractError('invalid strict JSON') from error


def safe_file(path, root=None):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ContractError('symlink refused')
    if root is not None and not path.is_relative_to(Path(root).absolute()):
        raise ContractError('path escapes bundle')
    if not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ContractError('missing or oversized evidence file')
    if path.name.endswith('.env') or '.local.env' in path.name:
        raise ContractError('credential files are not evidence')
    return path


def read_json(path):
    return loads(safe_file(path).read_bytes())


def relative_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ContractError('invalid bundle path')
    rel = PurePosixPath(name)
    if rel.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ContractError('invalid bundle path')
    return safe_file(Path(root) / rel, root)


def validate_hash(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ContractError('SHA-256 required')
    return value


def require_keys(obj, required, optional=()):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise ContractError('missing or unsupported fields')


def positive(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ContractError(name + ' must be a bounded positive integer')
    return value


def save(path, value, secret=''):
    _checkpoint(Path(path), _clean(value, secret))


def write_manifest(root):
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ContractError('symlink evidence refused')
        if path.is_file() and path.relative_to(root).as_posix() not in ('manifest.json', 'manifest.sha256'):
            files[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    save(root / 'manifest.json', {'schema': 'identity-evidence-v1', 'files': files,
                                 'scope': 'local_integrity_not_supplier_authentication'})
    (root / 'manifest.sha256').write_text(digest((root / 'manifest.json').read_bytes()) + '\n')
    os.chmod(root / 'manifest.sha256', 0o600)
    return files


def verify_manifest(root, expected=None):
    root = Path(root)
    raw = safe_file(root / 'manifest.json').read_bytes()
    declared = safe_file(root / 'manifest.sha256').read_text().strip()
    if digest(raw) != validate_hash(expected or declared) or digest(raw) != declared:
        raise ContractError('manifest hash mismatch')
    manifest = loads(raw)
    require_keys(manifest, ('schema', 'files', 'scope'))
    if manifest['schema'] != 'identity-evidence-v1' or not isinstance(manifest['files'], dict):
        raise ContractError('unsupported manifest')
    for name, sha in manifest['files'].items():
        if digest(relative_file(root, name).read_bytes()) != validate_hash(sha):
            raise ContractError('evidence hash mismatch: ' + name)
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ContractError('symlink evidence refused')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and p.relative_to(root).as_posix() not in ('manifest.json', 'manifest.sha256')}
    if actual != set(manifest['files']):
        raise ContractError('unlisted or missing evidence')
    return {'valid': True, 'files': len(actual), 'manifest_sha256': digest(raw),
            'externally_pinned': expected is not None}

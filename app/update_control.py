"""Fixed update requests for the host supervisor; no shell or download execution."""
import json
import os
import tempfile
from . import VERSION, config, host_setup

RELEASES_URL = 'https://github.com/Zwart04/agenmini/releases/latest'
SUPPORT_URL = 'https://tako.id/Zwart04/gift'


def managed():
    return host_setup.status()['managed']


def state():
    try:
        path = config.DATA_DIR / 'update-status.json'
        value = json.loads(path.read_text(encoding='utf-8')) if path.stat().st_size <= 16384 else {}
        if not isinstance(value, dict): value = {}
    except (OSError, ValueError): value = {}
    pending = any((config.DATA_DIR / name).exists() for name in ('update-request', 'update-processing'))
    message = value.get('message', '')
    if not isinstance(message, str): message = ''
    if pending:
        message = 'Menunggu tugas atau pemasangan harness selesai, lalu supervisor memeriksa update.' if any(
            (config.DATA_DIR / name).exists() for name in ('model-busy', 'task-busy', 'harness-install-busy', 'harness-run-busy')) else 'Permintaan update sedang diproses supervisor. Aplikasi dapat tersambung ulang setelah restart.'
    return {'version': VERSION, 'auto': (config.DATA_DIR / 'auto-update.enabled').exists(),
            'managed': managed(), 'pending': pending, 'message': message,
            'checked_at': value.get('checked_at', '') if isinstance(value.get('checked_at', ''), str) else '',
            'repository': 'https://github.com/Zwart04/agenmini', 'releases_url': RELEASES_URL}


def request(data):
    if not isinstance(data, dict) or not data or set(data) - {'auto', 'check', 'install'}:
        raise ValueError('Pilih cek versi, update, atau pengaturan otomatis.')
    if any(type(value) is not bool for value in data.values()) or data.get('check') and data.get('install'):
        raise ValueError('Tindakan update tidak valid.')
    if not managed():
        raise ValueError('Instalasi ini memakai installer/manual. Unduh update resmi: ' + RELEASES_URL)
    action = 'install' if data.get('install') else 'check' if data.get('check') else ''
    if action:
        target = config.DATA_DIR / 'update-request'
        if target.exists() or (config.DATA_DIR / 'update-processing').exists():
            raise ValueError('Permintaan update sebelumnya masih diproses. Tunggu status selesai.')
        # Publish a complete file without replacing an already queued request.
        # The supervisor must never observe an empty, newly created marker.
        with tempfile.NamedTemporaryFile(dir=config.DATA_DIR, prefix='.update-', delete=False) as stream:
            temporary = config.DATA_DIR / stream.name
            stream.write(action.encode('ascii'))
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ValueError('Permintaan update sebelumnya masih diproses.') from exc
        finally:
            temporary.unlink(missing_ok=True)
    if 'auto' in data:
        marker = config.DATA_DIR / 'auto-update.enabled'
        marker.write_text('1', encoding='utf-8') if data['auto'] else marker.unlink(missing_ok=True)
    return {'ok': True, **state()}

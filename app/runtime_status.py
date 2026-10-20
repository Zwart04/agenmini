"""Report actual local readiness separately from a saved model preference."""
import json
import os
import time
import aiohttp
from . import config, db, llm

_context_cache = {}


async def context_window():
    """Use llama-server's slot capacity, not the GGUF's theoretical maximum."""
    base = os.environ.get('LOCAL_API_BASE', 'http://local:8080/v1').rstrip('/').removesuffix('/v1')
    key = (base, db.setting('local_model_id'))
    cached = _context_cache.get(key)
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    capacity = 4096  # The bundled CPU server's configured fallback.
    try:
        async with llm.session().get(base + '/props', timeout=aiohttp.ClientTimeout(total=1)) as response:
            if response.status == 200:
                data = await response.json()
                value = data.get('default_generation_settings', {}).get('n_ctx')
                if type(value) is int and 256 <= value <= 2097152:
                    capacity = value
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError, AttributeError):
        pass
    _context_cache.clear()
    _context_cache[key] = (time.monotonic(), capacity)
    return capacity


def stored():
    try: return json.loads((config.DATA_DIR / 'runtime-status.json').read_text())
    except (OSError, ValueError): return {}


async def state():
    result = stored()
    result['selected'] = db.setting('local_model_id') or 'qwenpaw-2b'
    result['ready'] = False
    pending = config.DATA_DIR / 'runtime-request'
    if pending.exists():
        return {**result, 'phase': 'queued', 'message': 'Menunggu supervisor VPS (sekitar 30 detik).'}
    from .chat_models import engines
    if llm.active_backend() != 'local' and db.setting('auto_local')!='1' and 'local' not in engines() and not any(b.get('backend') == 'local' for b in db.bots(active_only=True)):
        return {**result, 'phase': 'stopped', 'message': 'Model lokal berhenti saat mode API aktif.'}
    if (config.DATA_DIR / 'runtime-processing').exists() and result.get('phase') in ('preparing', 'downloading', 'verifying'):
        return result
    base = os.environ.get('LOCAL_API_BASE', 'http://local:8080/v1').removesuffix('/v1')
    try:
        async with llm.session().get(base + '/health', timeout=aiohttp.ClientTimeout(total=2)) as response:
            ok = response.status == 200
        if ok:
            async with llm.session().get(base + '/v1/models', timeout=aiohttp.ClientTimeout(total=2)) as response:
                models = (await response.json()).get('data', [])
            if any(m.get('id') == result['selected'] for m in models):
                return {**result, 'ready': True, 'phase': 'ready', 'message': 'Model terverifikasi dan siap untuk chat.'}
            return {**result, 'phase': 'failed', 'message': 'Model yang berjalan berbeda dari pilihan. Klik Unduh / perbaiki.'}
        return {**result, 'phase': 'loading', 'message': 'Server sedang memuat model ke RAM.'}
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError):
        if result.get('phase') == 'failed': return result
        age = time.time() - float(result.get('started_at', time.time()))
        failed = age > 180 or result.get('phase') == 'ready'
        return {**result, 'phase': 'failed' if failed else 'loading', 'message': 'Model tidak terhubung. Periksa log lokal lalu coba perbaiki.' if failed else 'Menunggu server model. Chat belum siap.'}


def request(mode, model=None):
    if os.name == 'nt':
        if mode in ('api','reconcile'):return
        raise ValueError('Pemasangan mesin lokal/gateway dikelola oleh supervisor Linux. Pada Windows gunakan API langsung untuk gateway/model yang sudah berjalan, atau pemasangan VPS melalui WSL/Docker.')
    if (config.DATA_DIR / 'runtime-request').exists() or (config.DATA_DIR / 'runtime-processing').exists():
        raise ValueError('Persiapan mode sedang berjalan. Tunggu selesai sebelum mengganti atau mengunduh ulang.')
    if model:
        (config.DATA_DIR / 'local-model-request').write_text(model)
    from .model_runtime import write_status
    write_status('queued', 'Menunggu supervisor VPS.', model_id=model, started_at=time.time())
    path = config.DATA_DIR / 'runtime-request'
    tmp = path.with_suffix('.tmp'); tmp.write_text(mode); tmp.replace(path)

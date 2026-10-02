"""Report actual local readiness separately from a saved model preference."""
import json
import os
import time
import aiohttp
from . import config, db, llm


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
    if llm.active_backend() != 'local' and 'local' not in engines() and not any(b.get('backend') == 'local' for b in db.bots(active_only=True)):
        return {**result, 'phase': 'stopped', 'message': 'Model lokal berhenti saat mode API aktif.'}
    if result.get('phase') in ('preparing', 'downloading', 'verifying', 'failed'):
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
    except (aiohttp.ClientError, TimeoutError):
        age = time.time() - float(result.get('started_at', time.time()))
        failed = age > 180 or result.get('phase') == 'ready'
        return {**result, 'phase': 'failed' if failed else 'loading', 'message': 'Model tidak terhubung. Periksa log lokal lalu coba perbaiki.' if failed else 'Menunggu server model. Chat belum siap.'}


def request(mode, model=None):
    if (config.DATA_DIR / 'runtime-request').exists() or (config.DATA_DIR / 'runtime-processing').exists():
        raise ValueError('Persiapan mode sedang berjalan. Tunggu selesai sebelum mengganti atau mengunduh ulang.')
    if model:
        (config.DATA_DIR / 'local-model-request').write_text(model)
    from .model_runtime import write_status
    write_status('queued', 'Menunggu supervisor VPS.', model_id=model, started_at=time.time())
    path = config.DATA_DIR / 'runtime-request'
    tmp = path.with_suffix('.tmp'); tmp.write_text(mode); tmp.replace(path)

"""FreeLLMAPI native admin adapter; credentials never leave the server response filter."""
import asyncio
import os
import time
import aiohttp
from . import db, llm

_token = ''
_expires = 0
_lock = asyncio.Lock()


def base(): return os.environ.get('FREELLMAPI_BASE', 'http://freellmapi:3001').rstrip('/')


async def request(method, path, body=None, *, public=False):
    global _token, _expires
    if not public and (not _token or time.time() > _expires):
        async with _lock:
            if not _token or time.time() > _expires:
                password = os.environ.get('FREELLMAPI_ADMIN_PASSWORD')
                if not password: raise ValueError('Jalankan pemasang terbaru untuk menyiapkan FreeLLMAPI.')
                data = await request('POST', '/api/auth/login', {'email': 'agenmini@localhost.local', 'password': password}, public=True)
                _token = data['token']; _expires = time.time() + 300
    headers = {} if public else {'Authorization': 'Bearer ' + _token}
    try:
        async with llm.session().request(method, base() + path, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
            data = await r.json(content_type=None)
            if r.status >= 400:
                if r.status == 401: _token = ''; _expires = 0
                raise ValueError('FreeLLMAPI menolak operasi (%s). Periksa provider, kunci dan log layanan.' % r.status)
            return data
    except (aiohttp.ClientError, TimeoutError):
        raise ValueError('FreeLLMAPI belum terhubung. Tunggu persiapan layanan atau periksa agen free-log.')


async def ensure_key():
    key = (await request('GET', '/api/settings/api-key'))['apiKey']
    db.set_setting('freellmapi_key', key)
    return key


async def models():
    key = await ensure_key()
    async with llm.session().get(base() + '/v1/models?available=true', headers={'Authorization': 'Bearer ' + key}, timeout=aiohttp.ClientTimeout(total=20)) as r:
        if r.status != 200: raise ValueError('Daftar model FreeLLMAPI belum dapat dibaca.')
        data = await r.json()
    # Router strategies are synthetic, and don't prove a provider is connected.
    rows = [{'id': m['id'], 'name': m.get('name', m['id']) + (' (alias kompatibilitas)' if m['id'].startswith('claude-') else ''), 'status': m.get('execution_status', '')}
            for m in data.get('data', []) if m.get('id')]
    return rows + [{'id': 'auto:smart', 'name': 'Strategi: kualitas', 'status':'strategi'}, {'id':'auto:fast','name':'Strategi: cepat','status':'strategi'}]


async def state():
    rows = await models()
    providers = (await request('GET', '/api/keys/providers')).get('providers', [])
    raw = await request('GET', '/api/keys')
    keys = raw if isinstance(raw, list) else raw.get('keys', [])
    return {'models': rows, 'active_model': db.setting('freellmapi_model') or 'auto:smart',
            'providers': [{'id': p['platform'], 'name': p['name'], 'keyless': p.get('keyless', False)} for p in providers],
            'connections': [{'id': k['id'], 'platform': k.get('platform'), 'label': k.get('label'), 'status': k.get('status')} for k in keys]}

"""Server-side 9router integration. Dashboard credentials never enter model context."""
import asyncio
import os
import time
import aiohttp
import jwt
from . import db, llm

_key_lock = asyncio.Lock()
PROVIDER_ALIASES = {'antigravity':'ag','claude':'cc','gemini-cli':'gc','github':'gh','codex':'cx'}

def provider_id(value):
    return PROVIDER_ALIASES.get(value, value)

DEVICE_PROVIDERS = ['github', 'kiro', 'kimi', 'kilocode', 'codebuddy-cn', 'codebuddy-intl',
                    'qoder', 'qoder-cn', 'grok-cli', 'muse', 'glm']
CODE_PROVIDERS = ['codex', 'claude', 'gemini-cli', 'antigravity', 'iflow']
API_PROVIDERS = ['openai', 'anthropic', 'gemini', 'deepseek', 'openrouter', 'groq', 'mistral', 'xai']


def base():
    return os.environ.get('ROUTER_BASE', 'http://router:20128').rstrip('/')


def headers():
    secret = os.environ.get('ROUTER_JWT_SECRET', '')
    if not secret:
        raise llm.LLMError('Integrasi 9router belum diperbarui. Jalankan pasang-vps.sh versi baru di VPS.')
    token = jwt.encode({'authenticated': True, 'iat': int(time.time()), 'exp': int(time.time()) + 300},
                       secret, algorithm='HS256')
    return {'Cookie': 'auth_token=' + token, **({'Authorization':'Bearer '+db.setting('compatible_key')} if db.setting('compatible_key') else {})}


async def request(method, path, body=None):
    # Paths are constructed by authenticated admin endpoints, never supplied by the model.
    try:
        async with llm.session().request(method, base() + path, json=body, headers=headers(),
                                        timeout=aiohttp.ClientTimeout(total=15), allow_redirects=False) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise llm.LLMError(f'9router ({response.status}): {str(data.get("error", "permintaan gagal"))[:250]}')
            return data
    except aiohttp.ClientConnectorError:
        raise llm.LLMError('9router belum berjalan atau alamatnya tidak terjangkau. Di Koneksi pilih 9router > Siapkan sumber ini, tunggu status siap, lalu perbarui daftar model. Instalasi Docker memakai router:20128; instalasi komputer dapat memakai ROUTER_BASE=http://127.0.0.1:20128.')


async def ensure_key():
    async with _key_lock:
        if db.setting('compatible_key'):
            return db.setting('compatible_key')
        result = await request('POST', '/api/keys', {'name': 'Agen Mini'})
        if not result.get('key'):
            raise llm.LLMError('9router tidak mengembalikan API key.')
        db.set_setting('compatible_key', result['key'])
        return result['key']


async def state():
    await ensure_key()
    providers, models, combos = await asyncio.gather(request('GET', '/api/providers'),
                        request('GET', '/api/models'), request('GET', '/api/combos'))
    # Only expose safe fields; upstream fields can change between releases.
    connections = [{k: c.get(k) for k in ('id', 'provider', 'name', 'email', 'isActive', 'testStatus')}
                   for c in providers.get('connections', [])]
    connected = {provider_id(c['provider']) for c in connections if c.get('isActive') is not False}
    catalogue=models.get('models', models.get('data',[]))
    available=[]
    for m in catalogue:
        mid=m.get('routedModel') or m.get('fullModel') or m.get('id')
        provider=provider_id(m.get('provider') or m.get('owned_by') or (mid or '').split('/')[0])
        if mid and provider in connected and not any(word in mid.lower() for word in ('image','tts','embedding','audio','veo','video')):
            available.append({'id':mid,'name':m.get('name') or m.get('model') or mid})
    available += [{'id': c['name'], 'name': c['name'] + ' (fallback)'} for c in (combos if isinstance(combos,list) else combos.get('combos', []))]
    return {'connections': connections, 'models': available, 'active_model': db.setting('model'),
            'device_providers': DEVICE_PROVIDERS, 'code_providers': CODE_PROVIDERS,
            'api_providers': API_PROVIDERS, 'key_ready': True, 'model_note': 'Katalog provider terhubung; ketersediaan/kuota setiap model dibuktikan saat diuji.'}

async def secure():
    """Enforce authentication on the owner-managed gateway, then provision its client key."""
    await request('PATCH','/api/settings',{'requireLogin':True,'requireApiKey':True})
    await ensure_key()

if __name__=='__main__':
    async def run():
        try:await secure()
        finally:
            if llm._session:await llm._session.close()
    asyncio.run(run())

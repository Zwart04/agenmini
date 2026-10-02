"""Server-side 9router integration. Dashboard credentials never enter model context."""
import asyncio
import os
import time
import aiohttp
import jwt
from . import db, llm

_key_lock = asyncio.Lock()
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
    return {'Cookie': 'auth_token=' + token}


async def request(method, path, body=None):
    # Paths are constructed by authenticated admin endpoints, never supplied by the model.
    async with llm.session().request(method, base() + path, json=body, headers=headers(),
                                    timeout=aiohttp.ClientTimeout(total=90), allow_redirects=False) as response:
        data = await response.json(content_type=None)
        if response.status >= 400:
            raise llm.LLMError(f'9router ({response.status}): {str(data.get("error", "permintaan gagal"))[:250]}')
        return data


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
    connected = {c['provider'] for c in connections if c.get('isActive') is not False}
    available = [{'id': m.get('routedModel') or m.get('fullModel'), 'name': m.get('name') or m.get('model')}
                 for m in models.get('models', []) if m.get('provider') in connected]
    available += [{'id': c['name'], 'name': c['name'] + ' (fallback)'} for c in combos.get('combos', [])]
    return {'connections': connections, 'models': available, 'active_model': db.setting('model'),
            'device_providers': DEVICE_PROVIDERS, 'code_providers': CODE_PROVIDERS,
            'api_providers': API_PROVIDERS, 'key_ready': True}

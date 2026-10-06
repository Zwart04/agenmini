"""Server-side 9router integration. Dashboard credentials never enter model context."""
import asyncio
import os
import time
import re
import json
import aiohttp
from datetime import datetime
import jwt
from pathlib import Path
from . import db, llm

_key_lock = asyncio.Lock()
PROVIDER_ALIASES = {'antigravity':'ag','claude':'cc','gemini-cli':'gc','github':'gh','codex':'cx','opencode':'oc'}

def provider_id(value):
    return PROVIDER_ALIASES.get(value, value)

DEVICE_PROVIDERS = ['github', 'kiro', 'kimi', 'kilocode', 'codebuddy-cn', 'codebuddy-intl',
                    'qoder', 'qoder-cn', 'grok-cli', 'muse', 'glm']
CODE_PROVIDERS = ['codex', 'claude', 'gemini-cli', 'antigravity', 'iflow']
API_PROVIDERS = ['openai', 'anthropic', 'gemini', 'deepseek', 'openrouter', 'groq', 'mistral', 'xai']
PROVIDER_CATALOG = json.loads(Path(__file__).with_name('provider-catalog.json').read_text(encoding='utf-8'))
PROVIDER_ALIASES.update({p['id']:p.get('alias',p['id']) for p in PROVIDER_CATALOG})
API_PROVIDERS = sorted(set(API_PROVIDERS) | {p['id'] for p in PROVIDER_CATALOG if p['category'] in ('apikey','freeTier','webCookie') or p['id']=='cursor' or 'apikey' in p.get('authModes',[]) or p.get('noAuth')})
GO_DEVICE_PROVIDERS = [p for p in DEVICE_PROVIDERS if p != 'glm'] + ['kimi-coding','freebuff']
GO_CODE_ROUTES = {'codex':'pkce','claude':'pkce','xai':'pkce','gitlab':'pkce','gemini-cli':'authcode','iflow':'authcode','antigravity':'antigravity','cline':'cline','xiaomi-mimo':'xiaomi-mimo','trae':'trae','windsurf':'windsurf','zed':'zed','kimchi':'kimchi'}
_engine_cache = None
_engine_at = 0

async def engine():
    global _engine_cache, _engine_at
    if _engine_cache is not None and time.monotonic()-_engine_at < 60: return _engine_cache
    try: info = await request('GET','/api/version')
    except llm.LLMError: info = {}
    _engine_cache = 'go' if info.get('goVersion') or info.get('engine') == 'agenmini-gateway' else 'node'
    _engine_at = time.monotonic()
    return _engine_cache

async def oauth_begin(provider, redirect):
    kind=await engine()
    device=provider in (GO_DEVICE_PROVIDERS if kind=='go' else DEVICE_PROVIDERS)
    from urllib.parse import quote
    if kind=='go':
        if provider=='freebuff': result=await request('POST','/api/oauth/freebuff/initiate',{})
        elif device: result=await request('POST','/api/oauth/device/start',{'provider':provider})
        else:
            route=GO_CODE_ROUTES.get(provider)
            if not route: raise ValueError('Provider ini memerlukan metode login khusus; belum tersedia.')
            result=await request('GET','/api/oauth/'+route+'/authorize?provider='+quote(provider,safe='')+'&redirect_uri='+quote(redirect,safe=''))
    else:
        result=await request('GET','/api/oauth/'+provider+('/device-code' if device else '/authorize?redirect_uri='+quote(redirect,safe='')))
    return kind,device,result

async def oauth_exchange(flow, payload):
    provider=flow['provider']
    if flow.get('engine')=='go':
        if provider=='freebuff':
            return await request('POST','/api/oauth/freebuff/poll',{k:flow['data'].get(k) for k in ('fingerprintId','fingerprintHash','expiresAt')})
        if flow['device']:
            return await request('POST','/api/oauth/device/poll',{'provider':provider,'device_code':flow['data'].get('device_code'),'session':flow['data'].get('session',{})})
        return await request('POST','/api/oauth/'+GO_CODE_ROUTES[provider]+'/exchange',{'provider':provider,**payload})
    return await request('POST','/api/oauth/'+provider+('/poll' if flow['device'] else '/exchange'),payload)


def base():
    return (os.environ.get('ROUTER_BASE') or ('http://router:20128' if Path('/.dockerenv').exists() else 'http://127.0.0.1:20128')).rstrip('/')


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



def model_locked(connection, model):
    value=connection.get('modelLocks',{}).get(model.split('/',1)[-1])
    if not value:return False
    try:
        expiry=float(value)
        if expiry>10**11:expiry/=1000
    except (ValueError,TypeError):
        try:expiry=datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
        except ValueError:return False
    return expiry>time.time()


_keyless_catalog = []
_keyless_at = 0

async def keyless_models():
    """Discover current public OpenCode free routes; never publish its paid catalog."""
    global _keyless_catalog, _keyless_at
    if time.monotonic() - _keyless_at < 120:
        return list(_keyless_catalog)
    try:
        async with llm.session().get('https://opencode.ai/zen/v1/models',
                headers={'Authorization':'Bearer public'}, timeout=aiohttp.ClientTimeout(total=3)) as response:
            if response.status != 200:
                return list(_keyless_catalog)
            data = await response.json()
        _keyless_catalog = [m['id'] for m in data.get('data', [])
            if isinstance(m, dict) and isinstance(m.get('id'), str)
            and re.fullmatch(r'[a-zA-Z0-9._-]{1,100}', m['id'])
            and (m['id'].endswith('-free') or m['id'] == 'big-pickle')][:100]
        _keyless_at = time.monotonic()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        pass
    return list(_keyless_catalog)


async def state():
    await ensure_key()
    kind=await engine()
    providers, models, combos = await asyncio.gather(request('GET', '/api/connections' if kind=='go' else '/api/providers'),
                        request('GET', '/api/models?connected=1'), request('GET', '/api/combos'))
    # Only expose safe fields; upstream fields can change between releases.
    connections=[]
    for c in (providers if isinstance(providers,list) else providers.get('connections',[])):
        row={k:c.get(k) for k in ('id','provider','name','email','isActive','testStatus','expiresAt')}
        error=str(c.get('lastError') or '')[:500]
        for key,value in c.items():
            if re.search('token|secret|key',key,re.I) and isinstance(value,str) and value:error=error.replace(value,'[rahasia]')
        quota=bool(re.search('quota|resource_exhausted|rate.?limit',error,re.I))
        auth=bool(re.search('invalid_grant|unauthorized|invalid.?token',error,re.I))
        row.update({'lastError':error,'available':c.get('isActive') not in (False,0) and not auth})
        if quota:row['testStatus']='Sebagian model terkena batas kuota; model lain tetap dapat dicoba'
        elif auth:row['testStatus']='Perlu login ulang'
        row['modelLocks']={k[len('modelLock_'):]:v for k,v in c.items() if k.startswith('modelLock_') and isinstance(v,(str,int,float))}
        connections.append(row)
    connected = {provider_id(c['provider']) for c in connections if c.get('isActive') not in (False,0)}
    catalogue=models.get('models', models.get('data',[]))
    available=[]
    for m in catalogue:
        mid=m.get('routedModel') or m.get('fullModel') or m.get('id')
        provider=provider_id(m.get('provider') or m.get('owned_by') or (mid or '').split('/')[0])
        keyless = models.get('mode') == 'connected' and not any(provider_id(c['provider']) == provider for c in connections)
        if mid and (provider in connected or keyless) and not any(word in mid.lower() for word in ('image','tts','embedding','audio','veo','video')):
            available.append({'id':mid,'name':m.get('name') or m.get('model') or mid,'ready':keyless or any(c['available'] and not model_locked(c,mid) for c in connections if provider_id(c['provider'])==provider), 'provider':provider, 'keyless':keyless})
    if models.get('mode') == 'connected' and any(m.get('keyless') and m['provider'] == 'oc' for m in available):
        try:
            disabled = await request('GET', '/api/models/disabled')
        except llm.LLMError:
            disabled = {}
        blocked = set(disabled.get('opencode', [])) | set(disabled.get('oc', []))
        for mid in await keyless_models():
            if mid not in blocked:
                available.append({'id':'opencode/'+mid, 'name':mid, 'provider':'oc', 'keyless':True, 'ready':True})
    # Upstream publishes both canonical and short aliases; show one choice per model.
    seen=set(); unique=[]
    for row in available:
        key=(row['provider'], row['id'].split('/',1)[-1])
        if key not in seen:
            seen.add(key);unique.append(row)
    available=unique
    available += [{'id': c['name'], 'name': c['name'] + ' (fallback)'} for c in (combos if isinstance(combos,list) else combos.get('combos', []))]
    kind=await engine()
    return {'connections': connections, 'models': available, 'active_model': db.setting('model'),
            'device_providers': GO_DEVICE_PROVIDERS if kind=='go' else DEVICE_PROVIDERS,
            'code_providers': list(GO_CODE_ROUTES) if kind=='go' else CODE_PROVIDERS,
            'api_providers': API_PROVIDERS, 'provider_catalog': PROVIDER_CATALOG, 'engine':kind,
            'key_ready': True, 'model_note': 'Model berasal dari provider terhubung; kuota dibuktikan saat diuji.'}

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

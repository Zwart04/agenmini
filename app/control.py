"""Owner dashboard API: skills, MCP, router and office. No container socket required."""
import asyncio
import json
import secrets
import time
import re
from urllib.parse import urlparse, parse_qs, quote
from aiohttp import web, ClientError
from . import VERSION, config, db, llm, memory, tools, mcp_bridge, router, office, runtime_status, free_router

routes = web.RouteTableDef()
_oauth = {}
_mcp_lock = asyncio.Lock()
_approval_lock = asyncio.Lock()


@web.middleware
async def errors(request, handler):
    try:
        return await handler(request)
    except (ValueError, llm.LLMError) as exc:
        return web.json_response({'error': str(exc)}, status=400)
    except ClientError:
        return web.json_response({'error':'Layanan belum terhubung. Periksa status dan coba kembali.'}, status=502)
    except asyncio.TimeoutError:
        return web.json_response({'error': 'Koneksi terlalu lama; coba kembali.'}, status=504)


@routes.post('/api/skills')
async def create_skill(request):
    data = await request.json()
    if not all(str(data.get(k, '')).strip() for k in ('name', 'when_to_use', 'steps')):
        raise ValueError('Nama, kapan dipakai, dan langkah skill wajib diisi.')
    scope = data.get('scope', 'shared')
    if scope != 'shared' and not db.bot(scope):
        raise ValueError('Bot tidak ditemukan.')
    sid, _ = memory.save_skill(scope, str(data['name'])[:100], str(data['when_to_use'])[:500],
                               str(data['steps'])[:8000], source='manual')
    return web.json_response({'id': sid})


def mcp_config():
    path = config.DATA_DIR / 'mcp.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'servers': {}}


@routes.get('/api/mcp')
async def list_mcp(request):
    safe = []
    for name, server in mcp_config()['servers'].items():
        safe.append({'name': name, 'url': server.get('url', ''), 'command': server.get('command', ''), 'args': server.get('args', []),
                     'allow_tools': server.get('allow_tools', []), 'read_only_tools': server.get('read_only_tools', []),
                     'has_credentials': bool(server.get('headers') or server.get('env'))})
    registered = [{'name': n, 'description': t.description, 'approval': bool(t.danger)}
                  for n, t in tools.REGISTRY.items() if n.startswith('mcp_')]
    return web.json_response({'servers': safe, 'tools': registered})


@routes.post('/api/mcp')
async def save_mcp(request):
    data = await request.json()
    name = str(data.get('name', ''))
    if not re.fullmatch(r'[a-zA-Z0-9_]{1,24}', name):
        raise ValueError('Nama MCP: 1–24 huruf, angka atau underscore.')
    server = mcp_config()['servers'].get(name, {})
    if 'bot_id' in data and not db.bot(data['bot_id']):
        raise ValueError('Bot tidak ditemukan.')
    if data.get('url'):
        parsed = urlparse(data['url'])
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('Alamat MCP tidak valid.')
        server = {**server, 'url': data['url']}
        server.pop('command', None)
        server.pop('args', None)
        if 'token' in data:
            server['headers'] = {'Authorization': 'Bearer ' + data['token']} if data['token'] else {}
    elif data.get('command'):
        if not isinstance(data.get('args', []), list):
            raise ValueError('Argumen command harus daftar JSON.')
        server = {**server, 'command': data['command'], 'args': data.get('args', [])}
        server.pop('url', None)
    else:
        raise ValueError('Isi URL atau command MCP.')
    for field in ('allow_tools', 'read_only_tools'):
        values = data.get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError('Daftar alat harus berupa daftar nama.')
        server[field] = values
    async with _mcp_lock:
        current = mcp_config()
        current['servers'][name] = server
        path = config.DATA_DIR / 'mcp.json'
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        pending.chmod(0o600)
        pending.replace(path)
        for n in list(tools.REGISTRY):
            if n.startswith(f'mcp_{name}_'):
                del tools.REGISTRY[n]
        failures = await mcp_bridge.register()
    if data.get('bot_id'):
        bot = db.bot(data['bot_id'])
        new_tools = [n for n in tools.REGISTRY if n.startswith(f'mcp_{name}_')]
        db.save_bot({**bot, 'tools': list(dict.fromkeys(bot['tools'] + new_tools))})
    return web.json_response({'ok': True, 'connection_errors': failures})


@routes.delete('/api/mcp/{name}')
async def remove_mcp(request):
    name = request.match_info['name']
    async with _mcp_lock:
        current = mcp_config()
        current['servers'].pop(name, None)
        path = config.DATA_DIR / 'mcp.json'
        path.write_text(json.dumps(current), encoding='utf-8')
        path.chmod(0o600)
        for key in list(tools.REGISTRY):
            if key.startswith(f'mcp_{name}_'):
                del tools.REGISTRY[key]
    return web.json_response({'ok': True})


@routes.post('/api/mcp/discover')
async def discover_mcp(request):
    data = await request.json()
    if data.get('name') and 'headers' not in data and 'token' not in data:
        saved = mcp_config()['servers'].get(data['name'], {})
        data = {**saved, **data}
    async with asyncio.timeout(30):
        async with mcp_bridge.connection(data) as client:
            result = await client.list_tools()
    return web.json_response({'tools': [{'name': t.name, 'description': t.description,
              'readonly_hint': bool(t.annotations and t.annotations.readOnlyHint)} for t in result.tools]})


@routes.get('/api/router')
async def router_state(request):
    return web.json_response(await router.state())


@routes.post('/api/router/provider')
async def add_provider(request):
    data = await request.json()
    if data.get('provider') not in router.API_PROVIDERS:
        raise ValueError('Provider API tidak dikenal.')
    result = await router.request('POST', '/api/providers', {k: data[k] for k in ('provider', 'apiKey', 'name') if k in data})
    return web.json_response({'ok': True})


@routes.delete('/api/router/provider/{id}')
async def del_provider(request):
    await router.request('DELETE', '/api/providers/' + quote(request.match_info['id'], safe=''))
    return web.json_response({'ok': True})


@routes.post('/api/router/model')
async def choose_model(request):
    data = await request.json()
    await router.ensure_key()
    model = str(data.get('model', '')).strip()
    if not model:
        raise ValueError('Pilih model terlebih dahulu.')
    db.set_setting('llm_backend', 'router')
    db.set_setting('model', model)
    db.set_setting('router_last_model', model)
    return web.json_response({'ok': True})


@routes.post('/api/router/combo')
async def combo(request):
    data = await request.json()
    if not isinstance(data.get('models'), list) or len(data['models']) < 2:
        raise ValueError('Isi minimal dua model untuk fallback.')
    result = await router.request('POST', '/api/combos', {'name': data.get('name'), 'models': data['models']})
    return web.json_response({'ok': True})


@routes.post('/api/router/oauth')
async def oauth_start(request):
    data = await request.json()
    provider = data.get('provider')
    if provider not in router.DEVICE_PROVIDERS + router.CODE_PROVIDERS:
        raise ValueError('Provider OAuth tidak didukung menu ini.')
    # Bound pending sessions and discard expired secrets.
    for key in list(_oauth):
        if _oauth[key]['expires'] < time.time():
            del _oauth[key]
    if len(_oauth) >= 20:
        raise ValueError('Terlalu banyak login tertunda.')
    flow_id = secrets.token_urlsafe(24)
    redirect = data.get('redirect_uri') or ('http://localhost:1455/auth/callback' if provider == 'codex' else 'http://localhost:8080/callback')
    device = provider in router.DEVICE_PROVIDERS
    path = '/api/oauth/' + provider + ('/device-code' if device else '/authorize?redirect_uri=' + quote(redirect, safe=''))
    result = await router.request('GET', path)
    _oauth[flow_id] = {'provider': provider, 'device': device, 'data': result, 'redirect': redirect,
                       'owner': request.cookies.get('agen_sesi'), 'expires': time.time() + min(int(result.get('expires_in', 600)), 900)}
    return web.json_response({'flow': flow_id, 'device': device, 'user_code': result.get('user_code'),
        'url': result.get('verification_uri_complete') or result.get('verification_uri') or result.get('authUrl'),
        'interval': max(5, int(result.get('interval', 5)))})


@routes.post('/api/router/oauth/{flow}')
async def oauth_finish(request):
    flow_id = request.match_info['flow']
    flow = _oauth.get(flow_id)
    if not flow or flow['expires'] < time.time() or flow['owner'] != request.cookies.get('agen_sesi'):
        raise ValueError('Login kedaluwarsa; mulai lagi.')
    body = await request.json()
    original = flow['data']
    if flow['device']:
        payload = {'deviceCode': original.get('device_code'), 'codeVerifier': original.get('codeVerifier'),
                   'extraData': {k: v for k, v in original.items() if k.startswith('_')}}
        action = 'poll'
    else:
        pasted = str(body.get('callback', '')).strip()
        if not pasted.startswith(('http://', 'https://')):
            raise ValueError('Tempel URL callback lengkap agar state OAuth bisa diverifikasi.')
        query = parse_qs(urlparse(pasted).query)
        if query.get('state', [''])[0] != original.get('state'):
            raise ValueError('State OAuth tidak sesuai; jangan gunakan callback dari login lain.')
        payload = {'code': query.get('code', [''])[0], 'state': original.get('state'),
                   'redirectUri': flow['redirect'], 'codeVerifier': original.get('codeVerifier')}
        action = 'exchange'
    result = await router.request('POST', f'/api/oauth/{flow["provider"]}/{action}', payload)
    success = bool(result.get('success') or result.get('connection'))
    pending = bool(result.get('pending'))
    if result.get('error') == 'slow_down':
        flow['interval'] = min(flow.get('interval', 5) + 5, 30)
    if success:
        _oauth.pop(flow_id, None)
    return web.json_response({'success': success, 'error': result.get('error'), 'pending': pending, 'interval': flow.get('interval', 5)})


@routes.get('/api/office')
async def workspace(request):
    office.init()
    rows = db.q('SELECT * FROM office_tasks ORDER BY id DESC LIMIT 40')
    for row in rows:
        if row.get('approval_id'):
            approval=db.one('SELECT tool,args,reason,status FROM approvals WHERE id=?',(row['approval_id'],))
            if approval and approval['status']=='menunggu':row['approval']=approval
    bots = [{'id': b['id'], 'name': b['name'], 'icon': b['icon'], **office.state(b['id'])}
            for b in db.bots(active_only=True)]
    return web.json_response({'bots': bots, 'tasks': rows, 'busy_model': llm.gate.current})


@routes.post('/api/office')
async def create_office_task(request):
    data = await request.json()
    if not str(data.get('text', '')).strip():
        raise ValueError('Tugas wajib diisi.')
    return web.json_response({'id': office.enqueue('owner', data.get('target'), data['text'],owner_task=True)})


@routes.get('/api/update')
async def update_state(request):
    path = config.DATA_DIR / 'update-status.json'
    status = json.loads(path.read_text()) if path.exists() else {}
    runtime_path = config.DATA_DIR / 'runtime-status.json'
    runtime = json.loads(runtime_path.read_text()) if runtime_path.exists() else {}
    return web.json_response({'runtime_message': runtime.get('message', ''), 'version': VERSION, 'auto': (config.DATA_DIR / 'auto-update.enabled').exists(),
                             'repository': 'https://github.com/Zwart04/agenmini', **status})


@routes.post('/api/update')
async def update_action(request):
    data = await request.json()
    marker = config.DATA_DIR / 'auto-update.enabled'
    if 'auto' in data:
        marker.write_text('1') if data['auto'] else marker.unlink(missing_ok=True)
    if data.get('check'):
        (config.DATA_DIR / 'update-request').write_text('check')
    if data.get('install'):
        (config.DATA_DIR / 'update-request').write_text('install')
    return web.json_response({'ok': True})


@routes.post('/api/mode')
async def change_mode(request):
    data = await request.json()
    mode = data.get('mode')
    if mode not in ('local', 'router', 'online', 'ollama', 'freellmapi'):
        raise ValueError('Mode tidak dikenal.')
    if office.presence:
        raise ValueError('Tunggu tugas aktif selesai sebelum mengganti mode.')
    if mode == 'router':
        runtime_status.request('api')
        db.set_setting('llm_backend', 'router')
        if db.setting('router_last_model'):
            db.set_setting('model', db.setting('router_last_model'))
    elif mode == 'local':
        # Host supervisor starts/stops llama.cpp; app cannot control Docker itself.
        from . import local_models
        catalogue = local_models.catalogue()
        previous = db.setting('local_model_id')
        chosen = previous if any(m['id'] == previous and m['fits'] for m in catalogue['models']) else catalogue['recommended']
        if not chosen:
            raise ValueError('RAM belum terdeteksi atau tidak cukup. Tunggu status hardware, atau gunakan API.')
        runtime_status.request('local', chosen)
        db.set_setting('local_model_id', chosen)
        db.set_setting('llm_backend', 'local')
        db.set_setting('model', 'local')
    else:
        runtime_status.request('free' if mode == 'freellmapi' else 'api')
        db.set_setting('llm_backend', mode)
        if mode == 'freellmapi':
            db.set_setting('model', db.setting('freellmapi_model') or 'auto:smart')
        if mode == 'online':
            db.set_setting('model', 'online')
    return web.json_response({'ok': True, 'message': 'Mode disimpan. Persiapan layanan berjalan di latar; status akan diperbarui di halaman ini.'})


@routes.post('/api/skills/from-message')
async def verified_skill(request):
    from . import agent
    data = await request.json()
    return web.json_response({'message': await agent.save_verified_skill(int(data['message_id']))})

@routes.get('/api/office/log/{bot}')
async def office_log(request):
    bot = request.match_info['bot']
    if not db.bot(bot):
        raise ValueError('Bot tidak ditemukan.')
    rows = db.q("SELECT m.id,m.content,m.meta,m.created_at,c.channel FROM messages m JOIN chats c ON c.id=m.chat_id WHERE c.bot_id=? AND m.role='assistant' ORDER BY m.id DESC LIMIT 30", (bot,))
    for row in rows:
        meta = json.loads(row.pop('meta') or '{}')
        row['trace'] = [{'tool': t.get('alat'), 'result': str(t.get('hasil', ''))[:1200]} for t in meta.get('trace', [])]
    office.init()
    events = db.q('SELECT id,kind,text,created_at FROM office_events WHERE bot=? ORDER BY id DESC LIMIT 40',(bot,))
    return web.json_response({'entries': rows, 'events':events,'presence':office.state(bot)})

@routes.get('/api/local-models')
async def local_catalogue(request):
    from . import local_models
    result = local_models.catalogue()
    result['selected'] = db.setting('local_model_id') or 'qwenpaw-2b'
    result['runtime'] = await runtime_status.state()
    log = config.DATA_DIR / 'local-log.txt'
    result['log'] = log.read_text(errors='replace')[-6000:] if log.exists() else ''
    return web.json_response(result)

@routes.post('/api/local-models')
async def select_local_model(request):
    from . import local_models
    data = await request.json()
    model = next((m for m in local_models.catalogue()['models'] if m['id']==data.get('id')),None)
    if not model or not model['fits']:
        raise ValueError('Model tidak cocok dengan RAM terdeteksi. Pilih rekomendasi atau mode API.')
    if llm.gate.busy:
        raise ValueError('Tunggu tugas aktif selesai sebelum mengganti model.')
    if office.presence:
        raise ValueError('Tunggu semua tugas aktif selesai.')
    runtime_status.request('local', model['id'])
    db.set_setting('local_model_id',model['id'])
    db.set_setting('llm_backend','local')
    db.set_setting('model','local')
    return web.json_response({'ok':True,'message':'Model dipilih. VPS mengunduh dan memuatnya; lihat status atau agen lokal-log.'})

@routes.post('/api/office/approval/{id}')
async def office_approval(request):
    from . import agent
    data=await request.json()
    async with _approval_lock:
        task=db.one('SELECT * FROM office_tasks WHERE id=?',(int(request.match_info['id']),))
        if not task or task['status']!='waiting' or not task.get('approval_id'):
            raise ValueError('Permintaan izin ini sudah tidak berlaku.')
        db.run("UPDATE office_tasks SET status='working' WHERE id=?",(task['id'],))
        token=office.start(task['target'],task['text'])
        response=None
        try:
            response=await agent.resolve_approval(task['approval_id'],bool(data.get('ok')))
            db.run('UPDATE office_tasks SET result=?,status=?,approval_id=?,updated_at=? WHERE id=?',(response['text'][:6000],office.outcome(response),response.get('approval',0),time.time(),task['id']))
        except Exception as exc:
            db.run("UPDATE office_tasks SET status='failed',result=?,updated_at=? WHERE id=?",(str(exc)[:500],time.time(),task['id']))
            raise
        finally:office.finish(token,response)
    return web.json_response({'ok':True})


@routes.get('/api/freellmapi')
async def free_state(request):
    return web.json_response(await free_router.state())

@routes.post('/api/freellmapi/provider')
async def free_provider(request):
    data=await request.json()
    providers=(await free_router.request('GET','/api/keys/providers')).get('providers', [])
    if data.get('platform') not in [p['platform'] for p in providers]:
        raise ValueError('Provider tidak dikenal.')
    await free_router.request('POST','/api/keys',{'platform':data['platform'],'key':str(data.get('key','')).strip(),'label':str(data.get('label',''))[:100]})
    return web.json_response({'ok':True})

@routes.delete('/api/freellmapi/provider/{id}')
async def free_delete(request):
    key=int(request.match_info['id'])
    await free_router.request('DELETE','/api/keys/'+str(key))
    return web.json_response({'ok':True})

@routes.post('/api/freellmapi/model')
async def free_model(request):
    data=await request.json()
    ids=[m['id'] for m in await free_router.models()]
    if data.get('model') not in ids: raise ValueError('Model tidak tersedia pada server FreeLLMAPI.')
    db.set_setting('freellmapi_model',data['model'])
    if db.setting('llm_backend')=='freellmapi': db.set_setting('model',data['model'])
    return web.json_response({'ok':True})

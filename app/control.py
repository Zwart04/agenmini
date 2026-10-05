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


@routes.get('/api/customization')
async def customization_status(request):
    from . import customization, agent, repair
    bot = db.bot(request.query.get('bot', 'asisten'))
    if not bot:
        raise ValueError('Bot tidak ditemukan.')
    return web.json_response({'custom': db.setting('custom_harness') or '',
        'default_prompt': agent.default_system_prompt(bot), 'effective_prompt': agent.system_prompt(bot),
        'tools': bot['tools'], 'memory_scope': bot['memory_scope'],
        'versions': customization.versions('harness', 'shared'), 'files': repair.files(),
        'guard': 'Instruksi mengubah perilaku, bukan izin kode. Alat, folder, akun dan penjaga deploy tetap di luar instruksi AI.'})


@routes.post('/api/customization')
async def customization_save(request):
    from . import customization
    data = await request.json()
    if not isinstance(data, dict):
        raise ValueError('Gunakan objek pengaturan.')
    if data.get('action') == 'restore':
        customization.restore('harness', 'shared', int(data['version']))
    elif data.get('action') == 'default':
        customization.harness('')
    elif data.get('action') == 'save':
        customization.harness(data.get('text'))
    else:
        raise ValueError('Pilih save, restore atau default.')
    return web.json_response({'ok': True})


@routes.post('/api/memories/{id}/edit')
async def customization_memory_edit(request):
    from . import customization
    data = await request.json()
    if not isinstance(data, dict):
        raise ValueError('Gunakan objek pengaturan.')
    if data.get('action') == 'restore':
        customization.restore('memory', request.match_info['id'], int(data['version']))
    else:
        customization.edit_memory(int(request.match_info['id']), data.get('text'))
    return web.json_response({'ok': True})


@routes.get('/api/memories/{id}/versions')
async def customization_memory_versions(request):
    from . import customization
    return web.json_response({'versions': customization.versions('memory', request.match_info['id'])})


@routes.get('/api/repairs')
async def repair_status(request):
    from . import repair
    return web.json_response({'repairs': repair.status()})


@routes.post('/api/repairs')
async def repair_propose(request):
    from . import repair
    data = await request.json()
    if not isinstance(data, dict):
        raise ValueError('Gunakan objek permintaan.')
    return web.json_response(await repair.propose(data.get('prompt'), data.get('files'), data.get('bot', 'asisten')))


@routes.post('/api/repairs/{id}/cancel')
async def repair_cancel(request):
    from . import repair
    task = repair.tasks.get(request.match_info['id'])
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        repair.tasks.pop(request.match_info['id'], None)
    return web.json_response({'ok': True})


@routes.get('/api/repairs/{id}')
async def repair_detail(request):
    from . import repair
    return web.json_response(repair.detail(request.match_info['id']))


@routes.get('/api/repairs/{id}/download')
async def repair_download(request):
    from . import repair
    return web.Response(body=repair.archive(request.match_info['id']), content_type='application/zip', headers={'Content-Disposition': 'attachment; filename="agenmini-repair-draft.zip"', 'Cache-Control': 'no-store'})
_oauth = {}
_mcp_lock = asyncio.Lock()
_approval_lock = asyncio.Lock()
_tool_check_lock = asyncio.Lock()


@routes.post('/api/tools/check')
async def check_core_tools(request):
    """Harmless workspace roundtrip + real isolated Python; never sends external messages."""
    async with _tool_check_lock:
        rows = []
        bot=db.bot('teknisi') or db.bot('asisten')
        chat=db.chat_for(bot['id'],'diagnostic','owner')
        ctx=tools.Ctx(bot,chat,'web','web')
        name = '.agen-check-' + secrets.token_hex(12) + '.txt'
        try:
            await tools.write_file(ctx, name, 'Agen Mini · 1000')
            assert await tools.read_file(ctx, name) == 'Agen Mini · 1000'
            assert not (await tools.send_file(ctx, name)).startswith('Error:')
            rows.append({'name': 'Menulis, membaca, dan melampirkan berkas', 'ok': True, 'message': 'Roundtrip berkas UTF-8 berhasil.'})
        except Exception as exc:
            rows.append({'name': 'Berkas', 'ok': False, 'message': str(exc)[:200]})
        finally:
            tools._workpath(name).unlink(missing_ok=True)
        try:
            result = await tools._run_sandboxed(['python3', '-I', '-c', 'print(125*8)'], timeout=10)
            rows.append({'name': 'Python terisolasi', 'ok': result.strip() == '[kode keluar 0]\n1000', 'message': result[:200]})
        except Exception as exc:
            rows.append({'name': 'Python terisolasi', 'ok': False, 'message': str(exc)[:200]})
        builtin = 'mcp_agen_local_hardware'
        if builtin in tools.REGISTRY:
            try:
                result = await asyncio.wait_for(tools.REGISTRY[builtin].fn(ctx), 15)
                rows.append({'name': 'MCP hardware bawaan', 'ok': not str(result).startswith('Error:'), 'message': 'MCP menjawab permintaan.'})
            except Exception as exc:
                rows.append({'name': 'MCP hardware bawaan', 'ok': False, 'message': str(exc)[:200]})
        else:
            rows.append({'name': 'MCP hardware bawaan', 'ok': None, 'message': 'Tidak dipasang pada profil kosong.' if db.setting('setup_profile')=='blank' else 'Belum terdaftar; periksa koneksi MCP.'})
        return web.json_response({'checks': rows, 'note': 'Layanan API, GitHub/email, dan pembuat gambar memerlukan koneksi/kuota penyedia masing-masing. Uji ini tidak mengirim pesan keluar.'})


@routes.get('/api/chat-models/{bot}')
async def chat_model_choices(request):
    from . import chat_models
    bot = db.bot(request.match_info['bot'])
    if not bot: raise ValueError('Bot tidak ditemukan.')
    chat = db.chat_for(bot['id'], 'web', 'web')
    backend = request.query.get('backend', chat.get('backend') or '')
    return web.json_response({'models': await chat_models.choices(backend), 'backend': chat.get('backend') or '',
                             'model': (db.setting('local_model_id') if chat.get('backend') == 'local' else chat.get('model')) or '', 'default_backend': bot.get('backend') or db.setting('llm_backend'),
                             'default_model': bot.get('model') or llm.default_model(bot.get('backend'))})


@routes.post('/api/chat-models/{bot}')
async def chat_model_select(request):
    from . import chat_models
    bot = db.bot(request.match_info['bot'])
    if not bot: raise ValueError('Bot tidak ditemukan.')
    data = await request.json()
    chat = db.chat_for(bot['id'], 'web', 'web')
    return web.json_response(await chat_models.select(chat, str(data.get('backend', '')), str(data.get('model', ''))))


@routes.post('/api/local-models/inspect')
async def import_inspect(request):
    from . import model_import
    data = await request.json()
    return web.json_response({'models': await model_import.inspect(data.get('source'), data.get('name'))})


@routes.post('/api/local-models/import')
async def import_save(request):
    from . import model_import
    data = await request.json()
    rows = await model_import.inspect(data.get('source'), data.get('name'))
    selected = next((m for m in rows if m['id'] == data.get('id')), None)
    if not selected: raise ValueError('Berkas berubah atau tidak ditemukan. Periksa sumber lagi.')
    return web.json_response({'model': model_import.save(selected)})


@routes.get('/api/runtime')
async def engine_runtime(request):
    mode = db.setting('llm_backend')
    if mode == 'local': return web.json_response(await runtime_status.state())
    pending = (config.DATA_DIR / 'runtime-request').exists()
    preparing = (config.DATA_DIR / 'runtime-processing').exists()
    if pending or preparing:
        return web.json_response({'phase': 'queued' if pending else 'preparing', 'message': 'Menunggu supervisor VPS.' if pending else 'Menyiapkan layanan AI di VPS.', 'ready': False})
    if mode=='auto':
        from . import auto_router
        routes=await auto_router.discover()
        ready=any(route.get('ready') for route in routes)
        return web.json_response({'phase':'ready' if ready else 'stopped','ready':ready,'message':str(len(routes))+' kandidat router terdeteksi. Model aktual dan galat dicatat ketika digunakan.' if routes else 'Belum ada kandidat. Hubungkan provider atau siapkan lokal di Koneksi.'})
    if mode in ('router', 'compatible', 'freellmapi'):
        base, path = (free_router.base(), '/api/ping') if mode == 'freellmapi' else (router.base(), '/health')
        try:
            import aiohttp
            async with llm.session().get(base + path, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    return web.json_response({'phase': 'ready', 'ready': True, 'message': 'Layanan terhubung. Pilih model dari provider yang telah disambungkan.'})
        except (ClientError, TimeoutError): pass
        return web.json_response({'phase': 'loading', 'ready': False, 'message': 'Menunggu layanan AI. Periksa log jika berlangsung lama.'})
    return web.json_response({'phase': 'ready' if llm.online_ready() else 'stopped', 'ready': llm.online_ready(),
                              'message': 'Konfigurasi API tersimpan; koneksi dan model diuji saat mengirim pesan.' if llm.online_ready() else 'Isi URL, kunci API, dan ID model terlebih dahulu.'})


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
    if model not in {m['id'] for m in (await router.state())['models']}:
        raise ValueError('Model tidak tersedia dari provider 9router yang terhubung. Perbarui daftar model dahulu.')
    runtime_status.request('api')
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
    from . import office_learning
    bots = [{'id': b['id'], 'name': b['name'], 'icon': b['icon'], 'team':office_learning.team(b), **office.state(b['id'])}
            for b in db.bots(active_only=True)]
    return web.json_response({'bots': bots, 'tasks': rows, 'busy_model': llm.gate.current})


@routes.get('/api/office/learning')
async def learning_status(request):
    from . import office_learning,usage_meter
    return web.json_response({'learning':office_learning.status(),'usage':usage_meter.summary()})

@routes.post('/api/office/learning')
async def learning_settings(request):
    from . import office_learning
    data=await request.json()
    minutes=int(data.get('minutes',60));budget=int(data.get('daily_budget',60000))
    if minutes not in (15,60,0) or not 2000<=budget<=200000:raise ValueError('Jadwal atau batas token belum valid.')
    db.set_setting('office_idle_enabled','1' if data.get('enabled') and minutes else '0')
    db.set_setting('office_idle_minutes',str(minutes or 60));db.set_setting('office_idle_budget',str(budget))
    return web.json_response({'ok':True})

@routes.post('/api/office/discuss')
async def learning_discuss(request):
    from . import office_learning
    return web.json_response(await office_learning.discuss(manual=True))

@routes.post('/api/office/discussions/{id}/accept')
async def accept_learning(request):
    from . import office_learning
    office_learning.init();did=int(request.match_info['id']);row=db.one('SELECT * FROM office_discussions WHERE id=?',(did,))
    if not row or row['status']!='draft' or row['accepted']:raise ValueError('Saran ini belum dapat disimpan atau sudah disimpan.')
    mid,_=memory.add_memory('orchestrator','pelajaran','Pelajaran yang ditinjau pemilik: '+row['result'][:1400])
    if not mid:raise ValueError('Pelajaran belum memiliki isi yang cukup.')
    db.run('UPDATE office_discussions SET accepted=1 WHERE id=?',(did,))
    return web.json_response({'ok':True,'memory_id':mid})

@routes.post('/api/office/usage')
async def usage_settings(request):
    from . import usage_meter
    import math
    data=await request.json();currency=data.get('currency','USD')
    if currency not in ('USD','IDR','EUR','GBP','CNY','JPY','SGD','AUD'):raise ValueError('Mata uang belum didukung.')
    db.set_setting('office_currency',currency)
    if data.get('model'):
        model=str(data['model']);backend=data.get('backend')
        if len(model)>200 or backend not in ('local','router','freellmapi','online','compatible','ollama'):raise ValueError('Provider/model belum valid.')
        prices={key:float(data[key]) for key in ('input','output')}
        if any(not math.isfinite(v) or v<0 or v>10000 for v in prices.values()):raise ValueError('Tarif harus angka positif dalam USD per 1 juta token.')
        tariffs=usage_meter.tariffs();tariffs[backend+'|'+model]=prices;db.set_setting('model_tariffs',json.dumps(tariffs))
    return web.json_response({'ok':True})

@routes.post('/api/office/currency')
async def refresh_currency(request):
    from . import usage_meter
    return web.json_response(await usage_meter.refresh_rates())

@routes.delete('/api/office/history')
async def clear_office_history(request):
    from . import workspace_records
    return web.json_response({'ok':True,**workspace_records.clear_activity(request.query.get('scope','finished'))})


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
    if mode not in ('auto','local', 'router', 'online', 'ollama', 'freellmapi'):
        raise ValueError('Mode tidak dikenal.')
    if office.presence:
        raise ValueError('Tunggu tugas aktif selesai sebelum mengganti mode.')
    import os
    if os.name=='nt' and mode in ('local','router','freellmapi','ollama'):raise ValueError('Pada Windows pilih API langsung, isi URL /v1 gateway/model yang sudah berjalan dan API key. Pemasangan lokal/9router/FreeLLMAPI otomatis tersedia pada VPS Linux atau WSL/Docker.')
    if mode == 'auto':
        if db.setting('llm_backend') in ('router','compatible'):db.set_setting('auto_9router','1')
        runtime_status.request('reconcile')
        db.set_setting('llm_backend','auto'); db.set_setting('model','smart')
    elif mode == 'router':
        runtime_status.request('api')
        db.set_setting('llm_backend', 'router')
        db.set_setting('model', db.setting('router_last_model') or '')
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

@routes.get('/api/auto-router')
async def auto_router_state(request):
    from . import auto_router
    return web.json_response(await auto_router.status())

@routes.post('/api/auto-router')
async def auto_router_settings(request):
    data=await request.json()
    order=data.get('order',['online','router','freellmapi','local'])
    if not isinstance(order,list) or sorted(order)!=sorted(['freellmapi','router','online','local']):raise ValueError('Urutan mesin router tidak valid.')
    if office.presence or llm.gate.busy:raise ValueError('Tunggu tugas aktif selesai.')
    runtime_status.request('reconcile')
    db.set_setting('auto_route_order',','.join(order))
    db.set_setting('auto_9router','1' if data.get('router') else '0');db.set_setting('auto_local','1' if data.get('local') else '0')
    return web.json_response({'ok':True,'message':'Router disimpan. Layanan yang dipilih disiapkan supervisor; kandidat baru muncul setelah siap.'})

@routes.post('/api/ai/test')
async def ai_connection_test(request):
    data=await request.json();backend=data.get('backend') or db.setting('llm_backend')
    if backend not in ('auto','local','router','freellmapi','online'):raise ValueError('Mesin tidak dikenal.')
    token=llm.backend_context.set(backend);started=time.monotonic()
    try:
        result=await llm.chat([{'role':'system','content':'This is a connection instruction-following test. Output only the exact text AGEN_OK. No explanation or formatting.'},{'role':'user','content':'AGEN_OK'}],model=data.get('model') or llm.default_model(backend),max_tokens=256)
        return web.json_response({'ok':result['content'].strip()=='AGEN_OK','text':result['content'][:100], 'seconds':round(time.monotonic()-started,1),'model':result.get('stats',{}).get('served_model',''), 'routing':result.get('stats',{}).get('routing',{})})
    finally:llm.backend_context.reset(token)

@routes.get('/api/projects')
async def project_list(request):
    from . import project_jobs
    return web.json_response({'projects':project_jobs.rows()})

@routes.delete('/api/projects')
async def project_clear(request):
    from . import workspace_records
    return web.json_response({'ok':True,'cleared':workspace_records.clear_projects(request.query.get('scope','completed')),'files_preserved':True})

@routes.patch('/api/projects/{id}')
async def project_edit(request):
    from . import workspace_records
    workspace_records.update_project(int(request.match_info['id']),await request.json())
    return web.json_response({'ok':True})

@routes.delete('/api/projects/{id}')
async def project_delete(request):
    from . import workspace_records
    return web.json_response({'ok':True,**workspace_records.delete_project(int(request.match_info['id']))})

@routes.patch('/api/office/tasks/{id}')
async def office_edit(request):
    from . import workspace_records
    workspace_records.update_task(int(request.match_info['id']),await request.json())
    return web.json_response({'ok':True})

@routes.delete('/api/office/tasks/{id}')
async def office_delete(request):
    from . import workspace_records
    workspace_records.delete_task(int(request.match_info['id']))
    return web.json_response({'ok':True})

@routes.post('/api/projects')
async def project_create(request):
    from . import project_jobs
    data=await request.json()
    if not isinstance(data,dict):raise ValueError('Isi proyek harus berupa objek JSON.')
    name=data.get('name','')
    if not isinstance(name,str) or len(name)>180:raise ValueError('Nama proyek maksimal 180 karakter.')
    bot=db.bot('orchestrator')
    if not bot:raise ValueError('Profil kosong belum mempunyai Orchestrator. Tambahkan bot koordinator dengan alat proyek di Workspace > Tim bot terlebih dahulu.')
    ctx=tools.Ctx(bot,db.chat_for(bot['id'],'web','web'),'web','web')
    pid=project_jobs.create(ctx,data.get('brief',''),data.get('repository',''))
    if name.strip():db.run('UPDATE project_jobs SET name=? WHERE id=?',(name.strip(),pid))
    return web.json_response({'id':pid})

@routes.post('/api/projects/{id}/approval')
async def project_approval(request):
    from . import project_jobs,office,agent
    data=await request.json();pid=int(request.match_info['id'])
    async with _approval_lock:
        job=db.one('SELECT * FROM project_jobs WHERE id=?',(pid,))
        if not job or job['status']!='waiting' or not job['approval_id']:raise ValueError('Tidak ada izin tertunda pada proyek ini.')
        approval=db.one('SELECT status FROM approvals WHERE id=?',(job['approval_id'],))
        if not approval or approval['status']!='menunggu':raise ValueError('Izin ini sudah ditindaklanjuti.')
        ok=data.get('ok') is True
        response=await agent.resolve_approval(job['approval_id'],ok)
        current=db.one('SELECT status,approval_id FROM project_jobs WHERE id=?',(pid,))
        if current['status']=='waiting' and current['approval_id']==job['approval_id']:
            project_jobs.approval_completed(job['approval_id'],ok,response)
            current=db.one('SELECT status FROM project_jobs WHERE id=?',(pid,))
        state=current['status']
        return web.json_response({'ok':True,'status':state,'text':response.get('text','')})

@routes.post('/api/projects/{id}')
async def project_action(request):
    from . import project_jobs
    project_jobs.init();pid=int(request.match_info['id']);job=db.one('SELECT * FROM project_jobs WHERE id=?',(pid,))
    if not job:raise ValueError('Proyek tidak ditemukan.')
    data=await request.json();action=data.get('action')
    if 'autonomous' in data:
        if not isinstance(data['autonomous'],bool):raise ValueError('autonomous harus boolean.')
        db.run('UPDATE project_jobs SET autonomous=? WHERE id=?',(int(data['autonomous']),pid))
    if action=='pause':state='paused'
    elif action=='resume':
        if job['approval_id'] and (db.one('SELECT status FROM approvals WHERE id=?',(job['approval_id'],)) or {}).get('status')=='menunggu':raise ValueError('Izinkan atau tolak tindakan proyek terlebih dahulu.')
        state='queued'
    elif action=='replan' and job['status'] in ('failed','paused','review'):
        if job['approval_id'] and (db.one('SELECT status FROM approvals WHERE id=?',(job['approval_id'],)) or {}).get('status')=='menunggu':raise ValueError('Selesaikan izin tertunda sebelum menyusun ulang.')
        db.run("UPDATE project_jobs SET plan='{}',cursor=0 WHERE id=?",(pid,));state='queued'
    elif action=='accept' and job['status']=='review':state='done'
    else:raise ValueError('Tindakan proyek tidak valid.')
    if action=='resume':db.run('UPDATE project_jobs SET retry_count=0,next_run=0 WHERE id=?',(pid,))
    db.run('UPDATE project_jobs SET status=?,updated_at=? WHERE id=?',(state,time.time(),pid));project_jobs.event(pid,state,'Pemilik: '+action)
    return web.json_response({'ok':True})

@routes.get('/api/social')
async def social_status(request):
    from . import social_connections
    return web.json_response({'connections':social_connections.status()})

@routes.post('/api/social/{provider}')
async def social_configure(request):
    from . import social_connections
    provider=request.match_info['provider'];data=await request.json();action=data.get('action','save')
    if action=='save':social_connections.configure(provider,data);result={'ok':True}
    elif action=='start':result=social_connections.start(provider)
    elif action=='finish':result=await social_connections.finish(provider,data.get('callback',''))
    elif action=='verify':result=await social_connections.verify(provider)
    elif action=='disconnect':
        rows=social_connections.load();rows.pop(provider,None);social_connections.save(rows);result={'ok':True}
    else:raise ValueError('Tindakan koneksi belum dikenal.')
    return web.json_response(result)

@routes.get('/api/setup')
async def setup_status(request):
    from . import social_connections,integrations,profiles
    return web.json_response({'complete':db.setting('setup_complete')=='1','agent':profiles.status(),'social':social_connections.status(),'host':integrations.status(),'engine':db.setting('llm_backend'),'platform':__import__('platform').system(),'managed_runtime':__import__('os').name!='nt'})

@routes.post('/api/setup')
async def setup_done(request):
    from . import profiles
    data=await request.json()
    if not isinstance(data,dict):raise ValueError('Setup harus objek JSON.')
    if db.setting('setup_profile')=='pending':
        profiles.choose(data.get('profile'),data.get('full_access') is True)
        if data.get('profile') == 'template':
            from .main import activate_builtin_mcp
            errors = await activate_builtin_mcp()
            db.set_setting('setup_complete','1')
            return web.json_response({'ok':True,'mcp_errors':errors})
    db.set_setting('setup_complete','1');return web.json_response({'ok':True})

@routes.get('/api/learning')
async def learning_candidates(request):
    from . import learning
    return web.json_response(learning.status())

@routes.post('/api/learning/{id}')
async def learning_review(request):
    from . import learning
    data=await request.json()
    if not isinstance(data,dict):raise ValueError('Isi tinjauan harus objek JSON.')
    if data.get('action')=='refine':return web.json_response(await learning.refine(int(request.match_info['id'])))
    if data.get('action') not in ('accept','reject'):raise ValueError('Pilih terima atau tolak.')
    return web.json_response(learning.review(int(request.match_info['id']),data['action']=='accept',data.get('steps')))

@routes.get('/api/skills/{id}/versions')
async def skill_versions(request):
    from . import learning
    learning.init()
    return web.json_response({'versions':db.q('SELECT * FROM skill_versions WHERE skill_id=? ORDER BY id DESC',(int(request.match_info['id']),))})

@routes.post('/api/skills/{id}/restore')
async def restore_skill(request):
    from . import learning
    data=await request.json();learning.restore(int(request.match_info['id']),int(data['version']))
    return web.json_response({'ok':True})

@routes.post('/api/training/export')
async def export_training(request):
    from . import learning
    data=await request.json()
    if not isinstance(data,dict):raise ValueError('Isi ekspor harus objek JSON.')
    if data.get('include_private_conversations') is not True:raise ValueError('Konfirmasi ekspor percakapan privat diperlukan.')
    rows=learning.training_rows()
    body=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows)
    return web.Response(body=body.encode(),content_type='application/x-ndjson',headers={'Content-Disposition':'attachment; filename="agenmini-confirmed.jsonl"','Cache-Control':'no-store'})

@routes.get('/api/integrations')
async def host_integrations(request):
    from . import integrations
    return web.json_response(integrations.status())

@routes.post('/api/integrations/refresh')
async def refresh_integrations(request):
    marker=config.DATA_DIR/'integrations/refresh-request'
    marker.parent.mkdir(mode=0o700,exist_ok=True);marker.touch()
    return web.json_response({'ok':True,'message':'Deteksi ulang dijadwalkan melalui supervisor host.'})

@routes.get('/api/backup-vps')
async def download_vps_backup(request):
    path=config.DATA_DIR/'backup/vps-migration.tar.gz'
    if not path.is_file():raise ValueError('Backup migrasi belum dibuat. Pada host jalankan python3 /opt/agenmini/make_vps_backup.py. Arsip berisi kredensial privat; simpan dengan aman.')
    return web.FileResponse(path,headers={'Content-Disposition':'attachment; filename="agenmini-migrasi-vps.tar.gz"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@routes.get('/oauth/callback')
async def social_callback(request):
    from . import social_connections
    from html import escape
    state=request.query.get('state','')
    db.run('CREATE TABLE IF NOT EXISTS social_oauth(state TEXT PRIMARY KEY,provider TEXT,expires_at REAL,verifier TEXT)')
    flow=db.one('SELECT provider FROM social_oauth WHERE state=?',(state,))
    if not flow:raise ValueError('Login sudah selesai atau kedaluwarsa. Mulai login lagi di Koneksi.')
    result=await social_connections.finish(flow['provider'],str(request.url))
    return web.Response(text='<html lang="id"><meta name="viewport" content="width=device-width"><title>Koneksi Agen Mini</title><body style="font-family:system-ui;margin:40px;max-width:600px"><h1>Akun tersambung</h1><p>Akses baca terverifikasi: '+escape(result['account'])+'</p><a href="/">Kembali ke Agen Mini</a></body></html>',content_type='text/html')

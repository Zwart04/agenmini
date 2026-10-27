"""Agen Mini's own sequential routing over actual configured/ready endpoints."""
import asyncio
import time
import re
import contextvars
task_context=contextvars.ContextVar("auto_route_task",default="")
from . import db,llm,runtime_status,router,free_router
_cache=[];_at=0;_lock=asyncio.Lock();_cooldown={}


def provider_key(route):
    value=route.get('provider') or route['model'].split('/')[0]
    return route['backend'], router.provider_id(value)


def cooling(route):
    now=time.monotonic()
    return _cooldown.get((route['backend'],route['model']),0)>now or _cooldown.get(('provider',*provider_key(route)),0)>now


def failure_message(route, error):
    from .provider_errors import describe
    pid=provider_key(route)[1]
    name=next((p['name'] for p in router.PROVIDER_CATALOG if router.provider_id(p['id'])==pid),route['backend'])
    return name+': '+describe(error).message


def complex_request(messages):
    users=[str(m.get('content','')) for m in messages if m.get('role')=='user']
    text=(task_context.get() or (users[-1] if users else '')).split('[Pesan]')[-1][-14000:]
    return bool(re.search(r'kode|coding|python|shell|html|javascript|typescript|game|web.?app|aplikasi|repo|project|proyek|implement|debug|frontend|landing|architecture|complex|json_schema',text,re.I))


async def discover(force=False):
    global _cache,_at
    if not force and time.monotonic()-_at<30:return [dict(x) for x in _cache]
    async with _lock:
        if not force and time.monotonic()-_at<30:return [dict(x) for x in _cache]
        rows=[]
        async def collect(backend,fn):
            try:
                state=await asyncio.wait_for(fn(),5)
                if backend=='local':
                    if state['ready']:rows.append({'backend':'local','model':db.setting('local_model_id') or 'qwen35-08b','ready':True,'kind':'local'})
                else:
                    models=state.get('models',[])
                    connected=bool(state.get('connections')) or any(m.get('keyless') for m in models)
                    usable=[m for m in models if m.get('id') and m.get('ready') is not False and (backend=='router' or m.get('status')=='ready')]
                    if connected and usable:
                        # Prefer explicit models; synthetic strategies are not proof of a live provider.
                        for m in usable[:100]:rows.append({'backend':backend,'model':m['id'],'ready':True,'kind':'api','provider':m.get('provider') or m['id'].split('/')[0]})
            except (Exception,):pass
        # Reads are small; inference always uses llm's single gate.
        jobs=[collect('local',runtime_status.state)]
        if db.setting('auto_9router')=='1' or db.setting('compatible_key'):jobs.append(collect('router',router.state))
        if db.setting('freellmapi_key'):jobs.append(collect('freellmapi',free_router.state))
        await asyncio.gather(*jobs)
        if llm.online_ready():
            rows.append({'backend':'online','model':db.setting('online_model'),'ready':False,'kind':'api','configured':True})
        _cache=rows;_at=time.monotonic()
        return [dict(x) for x in rows]


async def candidates(messages):
    rows=await discover();complexity=complex_request(messages)
    preferences=db.setting('auto_route_order') or 'online,router,freellmapi,local'
    order=preferences.split(',')
    def rank(row):
        model=row['model'].lower();position=order.index(row['backend']) if row['backend'] in order else 9
        skill=next((i for i,key in enumerate(('medium','large','sonnet','gpt','small','ministral','devstral','codestral')) if key in model),9)
        if complexity:
            skill=next((i for i,key in enumerate(('devstral','codestral','opus','large','medium','sonnet','gpt','smart')) if key in model),9)
        if row['backend']=='local':return (10 if complexity else -1,0,0)
        preferred={'router':db.setting('router_last_model'),'freellmapi':db.setting('freellmapi_model'),'online':db.setting('online_model')}.get(row['backend'])
        return (position,-1 if not complexity and row['model']==preferred else skill,row['model'])
    rows.sort(key=rank)
    # Quotas can be model-specific. Bound retries while retaining other providers.
    selected=[];counts={};providers={}
    for row in rows:
        key=row['backend'];provider=(key,row.get('provider') or row['model'].split('/')[0])
        limit=4 if key=='router' else 2 if key=='freellmapi' else 1
        if counts.get(key,0)>=limit or cooling(row):continue
        if key=='router' and providers.get(provider,0)>=2:continue
        counts[key]=counts.get(key,0)+1;providers[provider]=providers.get(provider,0)+1
        selected.append({**row,'reason':'Coding/proyek: prioritaskan API yang terhubung.' if complexity else 'Tugas ringan: lokal siap didahulukan; API menjadi cadangan.'})
    if not selected:
        if rows and any(cooling(row) for row in rows):raise llm.LLMError('Koneksi sedang dijeda setelah provider menolak atau gagal merespons. Pilih provider lain/model lokal di Koneksi AI, atau coba kembali nanti.')
        raise llm.LLMError('Router Agen Mini belum memiliki kandidat siap. Hubungkan provider atau nyalakan model lokal melalui Koneksi.')
    return selected


def failed(route,seconds=60,error=None):
    from .provider_errors import describe
    failure=describe(error) if error is not None else None
    seconds=failure.seconds if failure else seconds
    _cooldown[(route['backend'],route['model'])]=time.monotonic()+seconds
    if failure and failure.provider_scope:_cooldown[('provider',*provider_key(route))]=time.monotonic()+seconds


async def status():
    return {'routes':await discover(),'order':(db.setting('auto_route_order') or 'online,router,freellmapi,local').split(','),
            'policy':'Heuristik berdasarkan jenis tugas dan koneksi aktual, bukan jaminan model terbaik. Lokal dipakai hanya saat server siap; retry serial terbatas per model/provider.'}

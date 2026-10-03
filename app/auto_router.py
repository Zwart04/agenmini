"""Agen Mini's own sequential routing over actual configured/ready endpoints."""
import asyncio
import time
import re
import contextvars
task_context=contextvars.ContextVar("auto_route_task",default="")
from . import db,llm,runtime_status,router,free_router
_cache=[];_at=0;_lock=asyncio.Lock();_cooldown={}


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
                    connected=bool(state.get('connections'))
                    usable=[m for m in models if m.get('id') and m.get('ready') is not False and (backend=='router' or m.get('status')=='ready')]
                    if connected and usable:
                        # Prefer explicit models; synthetic strategies are not proof of a live provider.
                        for m in usable[:100]:rows.append({'backend':backend,'model':m['id'],'ready':True,'kind':'api'})
            except (Exception,):pass
        # Reads are small; inference always uses llm's single gate.
        await asyncio.gather(collect('local',runtime_status.state),collect('freellmapi',free_router.state),collect('router',router.state))
        if db.setting('online_base') and db.setting('online_model') and db.setting('online_key'):
            rows.append({'backend':'online','model':db.setting('online_model'),'ready':False,'kind':'api','configured':True})
        _cache=rows;_at=time.monotonic()
        return [dict(x) for x in rows]


async def candidates(messages):
    rows=await discover();complexity=complex_request(messages)
    preferences=db.setting('auto_route_order') or 'freellmapi,router,online,local'
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
    # One candidate per API backend; retrying every model on the same quota wastes time.
    selected=[];seen=set()
    for row in rows:
        key=row['backend']
        if key in seen or _cooldown.get((key,row['model']),0)>time.monotonic():continue
        seen.add(key);selected.append({**row,'reason':'Coding/proyek: prioritaskan API yang terhubung.' if complexity else 'Tugas ringan: lokal siap didahulukan; API menjadi cadangan.'})
    if not selected:raise llm.LLMError('Router Agen Mini belum memiliki kandidat siap. Hubungkan provider atau nyalakan model lokal melalui Koneksi.')
    return selected


def failed(route,seconds=60):_cooldown[(route['backend'],route['model'])]=time.monotonic()+seconds


async def status():
    return {'routes':await discover(),'order':(db.setting('auto_route_order') or 'freellmapi,router,online,local').split(','),
            'policy':'Heuristik berdasarkan jenis tugas dan koneksi aktual, bukan jaminan model terbaik. Lokal dipakai hanya saat server siap; retry serial per backend.'}

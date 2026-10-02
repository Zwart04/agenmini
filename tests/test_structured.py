import pytest
from types import SimpleNamespace
from app import structured,workflow

@pytest.mark.asyncio
async def test_invalid_json_retries_once_before_using_selection(monkeypatch):
    calls=[];events=[]
    replies=iter([{'content':'{\n "bot": "teknisi\n','stats':{'finish_reason':'length'}},{'content':'```json\n{"bot":"teknisi"}\n```'}])
    async def chat(*a,**kw):calls.append(kw);return next(replies)
    async def event(*a):events.append(a)
    monkeypatch.setattr(structured.llm,'chat',chat)
    schema={'type':'object','properties':{'bot':{'enum':['teknisi']}},'required':['bot']}
    value,_=await structured.request([],label='Pemilihan',max_tokens=400,schema=schema,on_event=event)
    assert value=={'bot':'teknisi'} and len(calls)==2 and calls[1]['max_tokens']==800
    assert events

@pytest.mark.asyncio
async def test_invalid_json_never_becomes_partial_success(monkeypatch):
    attempts=[]
    async def chat(*a,**kw):attempts.append(kw);return {'content':'{"bot":"broken'}
    monkeypatch.setattr(structured.llm,'chat',chat)
    with pytest.raises(ValueError,match='setelah 2 percobaan') as err:
        await structured.request([],label='Pemilihan',max_tokens=400)
    assert len(attempts)==2 and 'Unterminated string' not in str(err.value)

@pytest.mark.asyncio
async def test_complete_json_with_length_finish_still_rejected(monkeypatch):
    async def chat(*a,**kw):return {'content':'{"bot":"teknisi"}','stats':{'finish_reason':'length'}}
    monkeypatch.setattr(structured.llm,'chat',chat)
    with pytest.raises(ValueError,match='terpotong'):await structured.request([],label='Pemilihan',max_tokens=400)

@pytest.mark.asyncio
async def test_schema_validation_retries_invalid_bot(monkeypatch):
    replies=iter([{'content':'{"bot":"invented"}'},{'content':'{"bot":"teknisi"}'}])
    async def chat(*a,**kw):return next(replies)
    monkeypatch.setattr(structured.llm,'chat',chat)
    value,_=await structured.request([],label='Pemilihan',max_tokens=400,schema={'type':'object','properties':{'bot':{'enum':['teknisi']}},'required':['bot']})
    assert value['bot']=='teknisi'

def test_continue_protected_project_does_not_choose_new_specialist(monkeypatch):
    from app import project_jobs
    monkeypatch.setattr(project_jobs,'init',lambda:None)
    monkeypatch.setattr(workflow.db,'q',lambda *a:[{'meta':'{"project_id":1}'}])
    monkeypatch.setattr(workflow.db,'one',lambda *a:{'id':1,'channel':'web','ext_id':'owner','repository':'https://github.com/Zwart04/ntpro','brief':'Repo yang jangan di sentuh:\n- https://github.com/Zwart04/ntpro','status':'paused'})
    ctx=SimpleNamespace(chat={'id':2},channel='web',ext_id='owner')
    result=workflow.previous_project(ctx,'lanjutkan dan laporkan ke telegram')
    assert result['meta']['project_id']==1 and result['meta']['status']=='paused'
    assert 'Repo dan salinan lokal dipertahankan' in result['text']

def test_continue_cannot_cross_channel_owner(monkeypatch):
    from app import project_jobs
    monkeypatch.setattr(project_jobs,'init',lambda:None)
    monkeypatch.setattr(workflow.db,'q',lambda *a:[{'meta':'{"project_id":1}'}])
    monkeypatch.setattr(workflow.db,'one',lambda *a:{'channel':'tg','ext_id':'another-owner'})
    assert workflow.previous_project(SimpleNamespace(chat={'id':2},channel='web',ext_id='owner'),'lanjutkan') is None

@pytest.mark.asyncio
async def test_streamed_truncation_is_detected_and_retried(monkeypatch):
    import json
    from aiohttp import web
    from app import llm
    requests=[]
    async def handler(request):
        requests.append(await request.json())
        text='{"bot":"unterminated' if len(requests)==1 else '{"bot":"teknisi"}'
        reason='length' if len(requests)==1 else 'stop'
        events=[{'model':'test-model','choices':[{'delta':{'content':text},'finish_reason':None}]},{'choices':[{'delta':{},'finish_reason':reason}]}]
        body=''.join('data: '+json.dumps(x)+'\n\n' for x in events)+'data: [DONE]\n\n'
        return web.Response(text=body,content_type='text/event-stream')
    app=web.Application();app.router.add_post('/chat/completions',handler)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    settings={'online_base':f'http://127.0.0.1:{port}','online_key':'test-only','online_model':'test-model'}
    monkeypatch.setattr(llm.db,'setting',lambda key:settings.get(key,''))
    async def chat(messages,**kwargs):return await llm._chat_online(messages,None,.2,kwargs.get('fmt'),max_tokens=kwargs['max_tokens'])
    monkeypatch.setattr(llm,'chat',chat)
    try:
        value,response=await structured.request([{'role':'user','content':'Choose JSON bot'}],label='Pemilihan',max_tokens=400)
        assert value=={'bot':'teknisi'} and len(requests)==2
        assert response['stats']['finish_reason']=='stop'
    finally:await runner.cleanup()

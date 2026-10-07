import asyncio
import json
import pytest
from app import db, deepseek_core, workbench, config
from test_harnesses import isolated

@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
@pytest.mark.parametrize('channel',['web','tg'])
async def test_shared_harness_executes_model_tools_on_every_backend_and_channel(isolated,monkeypatch,backend,channel):
    """Integration plumbing, not a live-provider quality benchmark."""
    from app import agent,llm
    db.set_setting('harness_mode','assisted');db.set_setting('full_access','1')
    db.set_setting('max_steps','2');db.set_setting('self_improve','off')
    bot=db.bot('orchestrator');bot.update(backend=backend,tools=['write_file'])
    filename=f'{backend}-{channel}.txt';payload=f'Unique model output for {backend}/{channel}'
    seen=[];calls=[]
    async def callback(kind,data):seen.append((kind,data))
    async def model(*args,**kwargs):
        assert llm.active_backend()==backend
        assert deepseek_core.current.get() is not None
        calls.append(backend)
        if len(calls)==1:
            return {'content':'','tool_calls':[{'name':'write_file','arguments':{'path':filename,'content':payload}}]}
        return {'content':payload,'tool_calls':[]}
    monkeypatch.setattr(llm,'chat',model)
    turn=agent.Turn(bot,channel,'shared-harness',callback)
    result=await turn.run('Jalankan tugas yang diberikan.')
    assert (config.WORK_DIR/filename).read_text(encoding='utf-8')==payload
    assert result['meta']['status']=='done'
    assert payload in result['text']
    rows=deepseek_core.events(turn.chat['id'])
    assert rows[0]['data']['channel']==channel
    lifecycle=[row for row in rows if row['kind'] in ('turn/start','tool/call','tool/result','turn/end')]
    assert [row['kind'] for row in lifecycle]==['turn/start','tool/call','tool/result','turn/end']
    assert lifecycle[2]['data']['outcome']=='returned'
    assert lifecycle[1]['data']['call_id']==lifecycle[2]['data']['call_id']
    assert deepseek_core.current.get() is None
    assert any(kind=='harness' and event['kind']=='turn/end' for kind,event in seen)

@pytest.mark.asyncio
async def test_interrupted_mutation_records_unknown_without_replay(isolated):
    chat=db.chat_for('orchestrator','core-test','cancel')
    seen=[]
    async def callback(kind,data):seen.append(data)
    core=deepseek_core.Core(chat['id'],'orchestrator',callback)
    started=asyncio.Event();calls=[]
    async def mutate():
        calls.append('started');started.set();await asyncio.Event().wait()
    task=asyncio.create_task(core.invoke('write_file',{'path':'a.txt','secret':'must-not-log'},mutate()))
    await started.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    await core.finish('interrupted')
    assert calls==['started']
    assert seen[-2]['code']=='TOOL_OUTCOME_UNKNOWN'
    rows=[r for r in deepseek_core.events(chat['id']) if r['run_id']==core.id]
    assert [r['kind'] for r in rows]==['tool/call','tool/result','turn/end']
    assert 'must-not-log' not in json.dumps(rows)

@pytest.mark.asyncio
async def test_failed_tool_and_file_change_are_not_synthetic_success(isolated):
    seen=[]
    async def callback(kind,data):seen.append(data)
    chat=db.chat_for('orchestrator','core-test','failed')
    core=deepseek_core.Core(chat['id'],'orchestrator',callback)
    async def operation():return 'Error: original failure'
    assert await core.invoke('run_shell',{},operation())=='Error: original failure'
    assert seen[-1]['outcome']=='error'
    token=deepseek_core.current.set(core)
    try:
        await deepseek_core.changed('a.js','old','new')
        await deepseek_core.changed('credentials.json','','private')
    finally:deepseek_core.current.reset(token)
    assert len([r for r in seen if r['kind']=='file/change'])==1

@pytest.mark.asyncio
@pytest.mark.parametrize('recover',[False,True])
async def test_deferred_batch_action_is_partial_until_actually_executed(isolated,monkeypatch,recover):
    from app import agent,llm
    db.set_setting('harness_mode','assisted');db.set_setting('full_access','1');db.set_setting('max_steps','2');db.set_setting('self_improve','off')
    bot=db.bot('orchestrator');bot.update(backend='online',tools=['write_file'])
    calls=[{'name':'write_file','arguments':{'path':f'part{i}.txt','content':f'actual {i}'}} for i in range(9)]
    replies=[{'content':'','tool_calls':calls}]
    if recover:replies.append({'content':'','tool_calls':[calls[-1]]})
    replies.append({'content':'Hasil tersedia.'})
    async def model(*args,**kwargs):
        response=replies.pop(0);response.setdefault('tool_calls',[]);return response
    monkeypatch.setattr(llm,'chat',model)
    result=await agent.Turn(bot,'web','batch-limit').run('Jalankan daftar tugas itu.')
    assert result['meta']['status']==('done' if recover else 'partial')
    assert (config.WORK_DIR/'part8.txt').exists()==recover

def test_workbench_rejects_traversal_private_binary_and_symlinks(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    for name in ('../app.py','.env','credentials.json','folder/token.txt','photo.png'):
        with pytest.raises(ValueError):workbench.target(name)
    p=tmp_path/'main.py';p.write_text('print(1)')
    assert workbench.file_info('main.py')['content']=='print(1)'

@pytest.mark.asyncio
async def test_editor_compare_and_swap_preserves_concurrent_agent_edit(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    monkeypatch.setattr(config,'DATA_DIR',tmp_path/'data')
    p=tmp_path/'a.js';p.write_text('first')
    original=workbench.file_info('a.js')
    p.write_text('agent changed')
    class Request:
        async def json(self):return {**original,'content':'user changed'}
    response=await workbench.save(Request())
    assert response.status==409 and p.read_text()=='agent changed'
    original=workbench.file_info('a.js')
    response=await workbench.save(Request())
    assert response.status==200 and p.read_text()=='user changed'

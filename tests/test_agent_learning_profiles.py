import json
import pytest
from app import db, config, main, profiles, learning, memory, tools, agent, telegram, llm


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    prior=db._conn
    monkeypatch.setattr(db,'_conn',None)
    for key,path in {'DATA_DIR':tmp_path,'DB_PATH':tmp_path/'db/agen.sqlite','WORK_DIR':tmp_path/'work','BACKUP_DIR':tmp_path/'backup','CERT_DIR':tmp_path/'cert'}.items():monkeypatch.setattr(config,key,path)
    # Detection is a separate integration; this fixture never scans the owner's host.
    original=main.Path.is_file
    monkeypatch.setattr(main.Path,'is_file',lambda self:False if self.name=='host-integrations.py' else original(self))
    main.bootstrap()
    yield
    db._conn.close()
    db._conn=prior


def completed():
    chat=db.chat_for('asisten','test','learning')
    db.add_message(chat['id'],'user','Simpan laporan produk sebagai berkas teks')
    mid=db.add_message(chat['id'],'assistant','Laporan tersimpan.',{'tools':['write_file'],'trace':[{'alat':'write_file','arg':'{"path":"secret-name.txt"}','hasil':'Tersimpan: secret-name.txt'}]})
    return mid


def test_blank_stays_empty_after_restarts(isolated):
    assert profiles.status()['profile']=='pending'
    assert len(db.bots())==1 and profiles.status()['skills']==profiles.status()['memories']==0
    profiles.choose('blank',True)
    main.bootstrap();main.bootstrap()
    assert db.setting('full_access')=='1' and not profiles.assisted()
    assert len(db.bots())==1 and profiles.status()['skills']==profiles.status()['memories']==0
    assert not (config.DATA_DIR/'mcp.json').exists()
    assert db.setting('self_improve')=='off'


def test_template_opt_in_does_not_invent_owner(isolated):
    profiles.choose('template')
    assert len(db.bots())==10 and db.bot('teknisi') and db.bot('pengingat')
    assert profiles.status()['skills']>0
    assert not memory.profile_memories(db.bot('asisten'))
    assert not db.one("SELECT id FROM memories WHERE text LIKE '%Davdigi%'")
    count=profiles.status()['skills'];main.bootstrap()
    assert count==profiles.status()['skills']
    with pytest.raises(ValueError):profiles.choose('blank')


def test_old_profile_is_preserved_but_false_preset_quarantined(isolated):
    text='Pemilik menjalankan Davdigi, bisnis pemasaran digital (iklan Meta & Google, CRM, pelacakan konversi).'
    db.set_setting('seed_done','["mem:bisnis"]');mid,_=memory.add_memory('shared','profil',text)
    profiles.quarantine_legacy()
    assert db.one('SELECT text FROM memories WHERE id=?',(mid,))['text']==text
    assert not memory.profile_memories(db.bot('asisten'))
    assert not memory.search_memories(db.bot('asisten'),'Davdigi')


def test_learning_single_real_tool_requires_review_and_is_idempotent(isolated):
    mid=completed();row=learning.stage(mid)
    assert row and row['status']=='pending' and profiles.status()['skills']==0
    assert 'secret-name.txt' not in row['steps']
    assert learning.stage(mid)['id']==row['id']
    accepted=learning.review(row['id'],True)
    assert accepted['skill_id'] and learning.review(row['id'],True)==accepted
    assert profiles.status()['skills']==1


def test_failed_cached_or_corrected_turn_never_becomes_skill(isolated):
    mid=completed()
    for meta in ({'status':'partial','trace':[{'alat':'write_file','hasil':'Tersimpan'}]},
                 {'trace':[{'alat':'write_file','hasil':'Error: missing'}]},
                 {'trace':[{'alat':'write_file','hasil':'Tersimpan','cached':True}]}):
        db.run('UPDATE messages SET meta=? WHERE id=?',(json.dumps(meta),mid));assert learning.stage(mid) is None
    mid=completed();row=learning.stage(mid);db.run('UPDATE messages SET feedback=-1 WHERE id=?',(mid,))
    with pytest.raises(ValueError):learning.review(row['id'],True)


def test_skill_revisions_restore_without_destroying_history(isolated):
    sid,_=memory.save_skill('asisten','Laporan','menulis laporan','write_file: tulis dan verifikasi berkas')
    memory.save_skill('asisten','Laporan','menulis laporan','write_file: tulis lalu read_file: baca ulang')
    v=db.one('SELECT * FROM skill_versions WHERE skill_id=?',(sid,));assert v['steps']=='write_file: tulis dan verifikasi berkas'
    learning.restore(sid,v['id']);assert db.one('SELECT steps FROM skills WHERE id=?',(sid,))['steps']==v['steps']
    assert db.one('SELECT count(*) n FROM skill_versions')['n']==2


@pytest.mark.asyncio
async def test_rating_toggle_does_not_inflate_scores(isolated):
    sid,_=memory.save_skill('asisten','Test','test','write_file: tulis berkas teks')
    mid=completed();db.run('UPDATE messages SET meta=? WHERE id=?',(json.dumps({'skills':[sid]}),mid))
    await agent.feedback(mid,True);await agent.feedback(mid,True,'');await agent.feedback(mid,False);await agent.feedback(mid,True)
    assert db.one('SELECT wins,fails FROM skills WHERE id=?',(sid,))=={'wins':1,'fails':0}


def test_private_training_export_excludes_unconfirmed_and_secrets(isolated):
    mid=completed();assert learning.training_rows()==[]
    db.run('UPDATE messages SET feedback=1 WHERE id=?',(mid,));assert len(learning.training_rows())==1
    db.run('UPDATE messages SET content=? WHERE id=?',('api_key=sk-private-secret-token-value',mid))
    assert learning.training_rows()==[]


@pytest.mark.asyncio
async def test_tool_discovery_cannot_expand_bot_permissions(isolated):
    bot={'id':'restricted','tools':['read_file','find_tools']};ctx=tools.Ctx(bot,{},'test','test')
    assert 'run_shell' not in await tools.find_tools(ctx,'execute shell command')
    result=await tools.find_tools(ctx,'read file');assert 'read_file' in result and ctx.exposed_tools==['read_file']


@pytest.mark.asyncio
async def test_telegram_does_not_offer_learning_for_greeting_or_failure(isolated,monkeypatch):
    tg=telegram.TgBot('TEST_ONLY');seen=[]
    async def edit(*args):seen.append(args)
    monkeypatch.setattr(tg,'edit',edit)
    for meta in ({},{'status':'partial','trace':[{'alat':'write_file','hasil':'Tersimpan'}]}):
        await tg.finish('1',1,{'text':'Jawaban dari model','message_id':completed(),'meta':meta})
        assert 'learn:' not in json.dumps(seen[-1])
    await tg.finish('1',1,{'text':'Berkas tersedia','message_id':completed(),'meta':{'trace':[{'alat':'write_file','hasil':'Tersimpan'}]}})
    assert 'learn:' in json.dumps(seen[-1])


@pytest.mark.asyncio
async def test_minimal_turn_keeps_model_reply_and_executes_real_file(isolated,monkeypatch):
    profiles.choose('blank');responses=[{'content':'','tool_calls':[{'name':'write_file','arguments':{'path':'answer.txt','content':'hasil unik 473'}}]}, {'content':'Hasil unik 473 sudah disimpan untuk permintaan Anda.','tool_calls':[]}]
    async def chat(*args,**kwargs):return responses.pop(0)|{'stats':{}}
    monkeypatch.setattr(llm,'chat',chat)
    result=await agent.Turn(db.bot('asisten'),'test','real-write').run('Simpan hasil unik sebagai berkas teks')
    assert '473' in result['text'] and (config.WORK_DIR/'answer.txt').read_text()=='hasil unik 473'
    assert learning.status()['candidates']==[]  # blank learning is opt-in

@pytest.mark.asyncio
async def test_correction_withdraws_accepted_evidence_but_preserves_manual_edits(isolated):
    mid=completed();row=learning.stage(mid)
    edited='write_file: pilih nama baru, tulis isi dan baca ulang hasilnya'
    accepted=learning.review(row['id'],True,edited)
    assert accepted['steps']==edited
    await agent.feedback(mid,False)
    assert db.one('SELECT active FROM skills WHERE id=?',(accepted['skill_id'],))['active']==0
    assert learning.stage(mid) is None
    mid=completed();accepted=learning.review(learning.stage(mid)['id'],True)
    db.run('UPDATE skills SET steps=?,source=? WHERE id=?',('Prosedur yang ditulis pemilik sendiri','manual',accepted['skill_id']))
    await agent.feedback(mid,False)
    assert db.one('SELECT active FROM skills WHERE id=?',(accepted['skill_id'],))['active']==1


@pytest.mark.asyncio
async def test_setup_and_training_apis_require_auth_and_explicit_choices(isolated):
    from aiohttp import web as aio
    from aiohttp.test_utils import TestClient,TestServer
    from app import control,web
    app=aio.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes);app.add_routes(web.routes)
    c=TestClient(TestServer(app));await c.start_server()
    headers={'Cookie':'agen_sesi='+web.make_token()}
    try:
        for path in ('/api/setup','/api/learning','/api/training/export'):
            r=await c.post(path,json={});assert r.status==401
        for body in ({},[],{'profile':'arbitrary'}):
            r=await c.post('/api/setup',headers=headers,json=body);assert r.status==400
        assert db.setting('setup_profile')=='pending'
        r=await c.post('/api/setup',headers=headers,json={'profile':'blank','full_access':False});assert r.status==200
        assert db.setting('harness_mode')=='minimal'
        r=await c.post('/api/training/export',headers=headers,json={});assert r.status==400
        r=await c.post('/api/training/export',headers=headers,json={'include_private_conversations':True})
        assert r.status==200 and await r.text()=='' and r.headers['Cache-Control']=='no-store'
    finally:await c.close()


def test_training_split_deduplicates_and_does_not_overwrite(tmp_path):
    from training.prepare_dataset import prepare
    source=tmp_path/'source.jsonl';out=tmp_path/'dataset'
    rows=[{'messages':[{'role':'user','content':f'Pertanyaan {i}'},{'role':'assistant','content':f'Jawaban {i}'}],'source_message_id':i} for i in range(12)]
    rows.append({'messages':[{'role':'user','content':' PERTANYAAN   0 '},{'role':'assistant','content':'duplicate'}]})
    source.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    assert prepare(source,out)['examples']==12
    a=[json.loads(s) for s in (out/'train.jsonl').read_text().splitlines()];b=[json.loads(s) for s in (out/'validation.jsonl').read_text().splitlines()]
    assert not {r['messages'][0]['content'] for r in a}&{r['messages'][0]['content'] for r in b}
    assert all(set(r)=={'messages'} for r in a+b)
    before=(out/'train.jsonl').read_bytes()
    with pytest.raises(ValueError):prepare(source,out)
    assert (out/'train.jsonl').read_bytes()==before

@pytest.mark.asyncio
async def test_successful_tool_followed_by_model_error_is_not_learned(isolated,monkeypatch):
    profiles.choose('blank');db.set_setting('self_improve','review')
    count=0
    async def fail_after_tool(*args,**kwargs):
        nonlocal count
        count+=1
        if count==1:return {'content':'','tool_calls':[{'name':'write_file','arguments':{'path':'partial.txt','content':'actual partial work'}}],'stats':{}}
        raise llm.LLMError('upstream unavailable')
    monkeypatch.setattr(llm,'chat',fail_after_tool)
    result=await agent.Turn(db.bot('asisten'),'test','failed-final').run('Simpan hasil pekerjaan dalam berkas')
    assert result['meta']['status']=='failed' and result['meta']['trace']
    assert (config.WORK_DIR/'partial.txt').exists()
    assert learning.stage(result['message_id']) is None and not learning.evidence(result['meta'])

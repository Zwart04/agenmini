import asyncio
import io
import json
import zipfile
import pytest
from app import agent, config, customization, db, llm, main, memory, repair


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    prior = db._conn
    monkeypatch.setattr(db, '_conn', None)
    for key, path in {'DATA_DIR':tmp_path, 'DB_PATH':tmp_path/'db/agen.sqlite', 'WORK_DIR':tmp_path/'work', 'BACKUP_DIR':tmp_path/'backup', 'CERT_DIR':tmp_path/'cert'}.items():
        monkeypatch.setattr(config, key, path)
    original = main.Path.is_file
    monkeypatch.setattr(main.Path, 'is_file', lambda self: False if self.name == 'host-integrations.py' else original(self))
    main.bootstrap()
    root = tmp_path/'source'; (root/'app').mkdir(parents=True); (root/'frontend').mkdir()
    (root/'app/sample.py').write_text('value = 1\n', encoding='utf-8')
    (root/'frontend/sample.js').write_text('const value = 1;\n', encoding='utf-8')
    monkeypatch.setattr(repair, 'ROOT', root)
    yield root
    assert not repair.tasks
    db._conn.close(); db._conn = prior


def test_harness_reset_and_restore_are_reversible(isolated):
    bot = db.bot('orchestrator'); baseline = agent.system_prompt(bot)
    customization.harness('Gunakan bahasa Indonesia yang ringkas.')
    assert agent.system_prompt(bot).endswith('Gunakan bahasa Indonesia yang ringkas.')
    customization.harness('')
    assert agent.system_prompt(bot) == baseline
    version = customization.versions('harness', 'shared')[0]
    customization.restore('harness', 'shared', version['id'])
    assert db.setting('custom_harness') == version['content']
    assert db.setting('full_access') != '1'


def test_memory_revision_updates_search_and_rejects_cross_record_restore(isolated):
    mid, _ = memory.add_memory('shared', 'fakta', 'kode lama phoenix')
    customization.edit_memory(mid, 'kode baru aurora')
    assert db.q("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'aurora'")
    assert not db.q("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'phoenix'")
    version = customization.versions('memory', mid)[0]
    with pytest.raises(ValueError): customization.restore('memory', mid+1, version['id'])
    customization.restore('memory', mid, version['id'])
    assert db.one('SELECT text FROM memories WHERE id=?', (mid,))['text'] == 'kode lama phoenix'


@pytest.mark.parametrize('name', ['../.env', 'app/../config.py', 'app/repair.py', 'app/config.py', '/app/sample.py', 'frontend\\sample.js', 'tests/test.py', '.github/workflows/test.yml'])
def test_code_guard_blocks_runtime_data_tests_and_traversal(isolated, name):
    with pytest.raises(ValueError): repair.source_path(name)


@pytest.mark.asyncio
async def test_real_draft_zip_preserves_live_source_and_has_no_installer(isolated, monkeypatch):
    original = (isolated/'app/sample.py').read_bytes()
    async def model(*args, **kwargs):
        return {'content': json.dumps({'summary':'Fix value', 'files':[{'path':'app/sample.py','content':'value = 2\n'}]}), 'stats':{}}
    monkeypatch.setattr(llm, 'chat', model)
    r = await repair.propose('Fix the sample value', ['app/sample.py'])
    await repair.tasks[r['id']]
    assert (isolated/'app/sample.py').read_bytes() == original
    assert repair.status()[0]['status'] == 'draft'
    with zipfile.ZipFile(io.BytesIO(repair.archive(r['id']))) as z:
        assert z.read('candidate/app/sample.py') == b'value = 2\n'
        assert b'-value = 1' in z.read('changes.diff')
        assert set(z.namelist()) == {'candidate/app/sample.py','changes.diff','manifest.json','README.txt'}
    (isolated/'app/sample.py').write_text('value = 3\n', encoding='utf-8')
    with pytest.raises(ValueError, match='kedaluwarsa'): repair.archive(r['id'])


@pytest.mark.asyncio
async def test_invalid_model_output_cannot_touch_application(isolated, monkeypatch):
    async def model(*args, **kwargs):
        return {'content':json.dumps({'files':[{'path':'app/sample.py','content':'not python !'}]})}
    monkeypatch.setattr(llm, 'chat', model)
    r = await repair.propose('Fix the invalid code', ['app/sample.py'])
    await repair.tasks[r['id']]
    assert repair.status()[0]['status'] == 'failed'
    assert (isolated/'app/sample.py').read_text() == 'value = 1\n'
    with pytest.raises(ValueError): repair.archive(r['id'])


@pytest.mark.asyncio
async def test_cancel_and_restart_leave_durable_failure_without_live_edits(isolated, monkeypatch):
    started = asyncio.Event()
    async def model(*args, **kwargs):
        started.set(); await asyncio.Event().wait()
    monkeypatch.setattr(llm, 'chat', model)
    r = await repair.propose('Fix sample code safely', ['app/sample.py'])
    await started.wait()
    with pytest.raises(ValueError, match='sedang'): await repair.propose('Second request', ['app/sample.py'])
    task = repair.tasks[r['id']]; task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert repair.status()[0]['status'] == 'interrupted'
    db.run("UPDATE app_repairs SET status='generating' WHERE id=?", (r['id'],))
    assert repair.status()[0]['status'] == 'interrupted'
    assert (isolated/'app/sample.py').read_text() == 'value = 1\n'


@pytest.mark.asyncio
async def test_edit_apis_require_owner_and_skill_manual_edits_have_versions(isolated):
    from aiohttp import web as aio
    from aiohttp.test_utils import TestClient, TestServer
    from app import control, web, learning
    app = aio.Application(middlewares=[control.errors, web.auth_mw]); app.add_routes(control.routes); app.add_routes(web.routes)
    c = TestClient(TestServer(app)); await c.start_server()
    headers = {'Cookie':'agen_sesi='+web.make_token()}
    try:
        for path in ('/api/customization','/api/repairs','/api/memories/1/edit'):
            assert (await c.post(path, json={})).status == 401
        assert (await c.post('/api/customization', headers=headers, json={'action':'save','text':'Use concise answers'})).status == 200
        sid, _ = memory.save_skill('shared','Procedure','when','old procedure step','verified')
        assert (await c.post('/api/skills/'+str(sid), headers=headers, json={'steps':'new step','when_to_use':'when','name':'Procedure'})).status == 200
        learning.init()
        assert db.one('SELECT * FROM skill_versions WHERE skill_id=?', (sid,))['steps'] == 'old procedure step'
        assert db.one('SELECT source FROM skills WHERE id=?', (sid,))['source'] == 'manual'
    finally:
        await c.close()

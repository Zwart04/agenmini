import json
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from app import db,main,control,tools,project_jobs,workspace_records,office,config
from app import web as auth
main.bootstrap(profile='template')

@pytest.mark.asyncio
async def test_project_and_activity_crud_preserve_files_and_conversations(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    app=web.Application(middlewares=[control.errors,auth.auth_mw]);app.add_routes(control.routes)
    async with TestClient(TestServer(app)) as client:
        headers={'Cookie':'agen_sesi='+auth.make_token()}
        denied=await client.delete('/api/projects?scope=all');assert denied.status==401
        count=db.one('SELECT count(*) n FROM project_jobs')['n']
        for invalid in ([],{'name':True,'brief':'invalid name'},{'brief':42},{'brief':'invalid repo','repository':True}):
            response=await client.post('/api/projects',headers=headers,json=invalid);assert response.status==400
        assert db.one('SELECT count(*) n FROM project_jobs')['n']==count
        ctx=tools.Ctx(db.bot('orchestrator'),db.chat_for('orchestrator','crud-test','private'),'crud-test','private')
        first=project_jobs.create(ctx,'Project CRUD regression');second=project_jobs.create(ctx,'Completed fixture')
        source=tmp_path/('projects/project-'+str(first));source.mkdir(parents=True);(source/'source.txt').write_text('must survive record removal')
        db.run("UPDATE project_jobs SET status='done' WHERE id=?",(second,))
        response=await client.patch('/api/projects/'+str(first),headers=headers,json={'name':'Changed','brief':'Actual revised goal'});assert response.status==200
        invalid=await client.patch('/api/projects/'+str(first),headers=headers,json=[]);assert invalid.status==400
        assert db.one('SELECT name,brief FROM project_jobs WHERE id=?',(first,))=={'name':'Changed','brief':'Actual revised goal'}
        project_jobs.running_projects.add(first)
        response=await client.delete('/api/projects?scope=all',headers=headers);assert response.status==400
        assert db.one('SELECT id FROM project_jobs WHERE id=?',(second,))
        project_jobs.running_projects.discard(first)
        response=await client.delete('/api/projects?scope=completed',headers=headers);assert response.status==200
        assert db.one('SELECT id FROM project_jobs WHERE id=?',(first,))
        assert not db.one('SELECT id FROM project_jobs WHERE id=?',(second,))
        response=await client.delete('/api/projects/'+str(first),headers=headers);assert response.status==200
        assert (source/'source.txt').read_text()=='must survive record removal'
        assert not db.one('SELECT id FROM project_events WHERE project_id=?',(first,))
        tid=office.enqueue('owner','teknisi','Old queued task',owner_task=True)
        response=await client.patch('/api/office/tasks/'+str(tid),headers=headers,json={'text':'Changed queued task'});assert response.status==200
        assert db.one('SELECT text FROM office_tasks WHERE id=?',(tid,))['text']=='Changed queued task'
        db.run("UPDATE office_tasks SET status='working' WHERE id=?",(tid,))
        response=await client.delete('/api/office/tasks/'+str(tid),headers=headers);assert response.status==400
        other=office.enqueue('owner','teknisi','Finished activity')
        db.run("UPDATE office_tasks SET status='done' WHERE id=?",(other,))
        chat=db.new_chat('teknisi','office',str(other));db.add_message(chat['id'],'assistant','History to clear')
        normal=db.new_chat('teknisi','web','crud-preserve');db.add_message(normal['id'],'assistant','Never remove normal chat')
        office.log('teknisi','done','Old activity')
        response=await client.delete('/api/office/history?scope=all',headers=headers);data=await response.json();assert response.status==200 and data['working']>=1
        assert not db.one('SELECT id FROM office_tasks WHERE id=?',(other,))
        assert db.one('SELECT id FROM office_tasks WHERE id=?',(tid,))
        assert not db.one('SELECT id FROM chats WHERE id=?',(chat['id'],))
        assert db.one('SELECT id FROM messages WHERE chat_id=?',(normal['id'],))
        assert db.one('SELECT count(*) n FROM office_events')['n']==0
        db.run("UPDATE office_tasks SET status='done' WHERE id=?",(tid,));await client.delete('/api/office/tasks/'+str(tid),headers=headers)
        db.delete_chat(normal['id'])

@pytest.mark.asyncio
async def test_chunked_read_keeps_project_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    folder=tmp_path/'projects/example';folder.mkdir(parents=True);(folder/'large.py').write_text('\n'.join('line-'+str(n) for n in range(1000)))
    ctx=tools.Ctx(db.bot('teknisi'),db.chat_for('teknisi','chunk-test','x'),'chunk-test','x');ctx.project_folder='projects/example'
    assert await tools.read_file(ctx,'large.py',start_line=901,max_lines=2)=='line-900\nline-901'
    with pytest.raises(ValueError):await tools.read_file(ctx,'../other/secret',start_line=1,max_lines=2)

def test_large_project_event_preserves_valid_json():
    ctx=tools.Ctx(db.bot('orchestrator'),db.chat_for('orchestrator','event-test','x'),'event-test','x');pid=project_jobs.create(ctx,'Event JSON regression')
    try:
        project_jobs.event(pid,'milestone',json.dumps({'step':3,'response':{'text':'Checked','meta':{'trace':[{'arg':'a'*800,'hasil':'b'*7000} for _ in range(40)]}}}))
        row=db.one('SELECT text FROM project_events WHERE project_id=? ORDER BY id DESC',(pid,));data=json.loads(row['text']);assert data['step']==3 and len(row['text'])<=10000
    finally:workspace_records.delete_project(pid)


def test_project_archive_includes_source_beyond_inventory_limit_and_excludes_runtime(tmp_path):
    import zipfile
    from app import project_archive
    root = tmp_path / 'source'
    root.mkdir()
    for index in range(501):
        (root / ('file-' + str(index) + '.txt')).write_text('actual source')
    for name in ('.env', 'app.db', 'app.db-wal', 'app.db-shm', 'key.pem'):
        (root / name).write_text('private fixture')
    destination = tmp_path / 'source.zip'
    report = project_archive.create_source_zip(root, destination)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == 502 and 'file-500.txt' in names
        assert not any(name in names for name in ('.env', 'app.db', 'app.db-wal', 'app.db-shm', 'key.pem'))
        assert json.loads(archive.read('AGENMINI-ARCHIVE.json'))['omitted'] == report['omitted']


def test_deleted_project_id_cannot_reuse_preserved_source_or_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'WORK_DIR', tmp_path)
    ctx = tools.Ctx(db.bot('orchestrator'), db.chat_for('orchestrator', 'id-safety', 'x'), 'id-safety', 'x')
    old = project_jobs.create(ctx, 'Preserved source regression')
    folder = tmp_path / ('projects/project-' + str(old))
    folder.mkdir(parents=True)
    (folder / 'important.txt').write_text('original repository')
    workspace_records.delete_project(old)
    archive_only = old + 1
    (tmp_path / ('projects/project-' + str(archive_only) + '-source.zip')).write_bytes(b'old archive fixture')
    new = project_jobs.create(ctx, 'New independent project')
    try:
        assert new > archive_only
        assert (folder / 'important.txt').read_text() == 'original repository'
        assert db.one('SELECT folder FROM project_jobs WHERE id=?', (new,))['folder'] != str(folder.relative_to(tmp_path))
    finally:
        workspace_records.delete_project(new)

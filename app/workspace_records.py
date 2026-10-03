"""Owner-facing records; deleting records never removes project source files."""

import time

from . import db, office, office_learning, project_jobs


def editable_project(project_id):
    project_jobs.init()
    job = db.one('SELECT * FROM project_jobs WHERE id=?', (project_id,))
    if not job:
        raise ValueError('Proyek tidak ditemukan.')
    if job['status'] in ('working', 'planning') or project_id in project_jobs.running_projects:
        raise ValueError('Tahap masih berjalan. Jeda dahulu dan tunggu tahap berhenti sebelum mengubah atau menghapus.')
    return job


def update_project(project_id, data):
    editable_project(project_id)
    fields = {}
    for field, limit in [('name', 180), ('brief', 12000)]:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(field + ' wajib berupa teks yang tidak kosong.')
        fields[field] = value.strip()
    if not fields:
        raise ValueError('Isi nama atau tujuan proyek.')
    assignments = ','.join(field + '=?' for field in fields)
    db.run('UPDATE project_jobs SET ' + assignments + ',updated_at=? WHERE id=?',
           (*fields.values(), time.time(), project_id))
    project_jobs.event(project_id, 'edited', 'Nama/tujuan diperbarui oleh pemilik; source dan checkpoint dipertahankan.')


def delete_project(project_id):
    job = editable_project(project_id)
    with db._lock:
        connection = db.conn()
        with connection:
            # db.conn uses autocommit; explicitly group related record deletions.
            connection.execute('BEGIN IMMEDIATE')
            if job.get('approval_id'):
                connection.execute("UPDATE approvals SET status='ditolak' WHERE id=? AND status='menunggu'",
                                   (job['approval_id'],))
            for table in ('project_events', 'project_stage_receipts', 'project_stage_snapshots'):
                connection.execute('DELETE FROM ' + table + ' WHERE project_id=?', (project_id,))
            connection.execute('DELETE FROM project_jobs WHERE id=?', (project_id,))
    return {'id': project_id, 'folder_preserved': job['folder']}


def clear_projects(scope):
    if scope not in ('completed', 'all'):
        raise ValueError('Pilih completed atau all.')
    project_jobs.init()
    rows = db.q('SELECT id,status FROM project_jobs')
    selected = [row for row in rows if scope == 'all' or row['status'] == 'done']
    # Validate every selected row before removing any, including paused stages still executing.
    for row in selected:
        editable_project(row['id'])
    for row in selected:
        delete_project(row['id'])
    return len(selected)


def task_record(task_id):
    office.init()
    row = db.one('SELECT * FROM office_tasks WHERE id=?', (task_id,))
    if not row:
        raise ValueError('Aktivitas tidak ditemukan.')
    if row['status'] == 'working':
        raise ValueError('Tugas masih berjalan; tunggu hasil sebelum mengubah atau menghapus.')
    return row


def delete_task(task_id):
    row = task_record(task_id)
    if row.get('approval_id'):
        db.run("UPDATE approvals SET status='ditolak' WHERE id=? AND status='menunggu'", (row['approval_id'],))
    db.run('DELETE FROM office_tasks WHERE id=?', (task_id,))


def update_task(task_id, data):
    row = task_record(task_id)
    if row['status'] != 'queued':
        raise ValueError('Hanya tugas yang belum dijalankan dapat diubah. Buat tugas baru untuk mengulang hasil lama.')
    text = data.get('text', row['text'])
    target = data.get('target', row['target'])
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('Isi tugas wajib berupa teks, maksimal 4000 karakter.')
    bot = db.bot(target)
    if not bot or not bot['active']:
        raise ValueError('Bot tidak tersedia.')
    db.run('UPDATE office_tasks SET text=?,target=?,updated_at=? WHERE id=?',
           (text.strip(), target, time.time(), task_id))
    office.task_event(task_id)


def clear_activity(scope='finished'):
    office.init()
    if scope not in ('finished', 'all'):
        raise ValueError('Pilih finished atau all.')
    query = ("SELECT id FROM office_tasks WHERE status!='working'" if scope == 'all'
             else "SELECT id FROM office_tasks WHERE status IN ('done','failed')")
    rows = db.q(query)
    for row in rows:
        delete_task(row['id'])
    if scope == 'all':
        # Explicit full clearing removes office history, preserving active tasks,
        # normal web/Telegram chats, saved lessons and token accounting.
        db.run('DELETE FROM office_events')
        chats = db.q("SELECT id FROM chats WHERE channel='office' AND ext_id NOT IN "
                     "(SELECT CAST(id AS TEXT) FROM office_tasks WHERE status='working')")
        for chat in chats:
            db.delete_chat(chat['id'])
        office_learning.init()
        db.run("DELETE FROM office_discussion_messages WHERE discussion_id IN "
               "(SELECT id FROM office_discussions WHERE status!='working')")
        db.run("DELETE FROM office_discussions WHERE status!='working'")
        office._recent.clear()
    working = db.one("SELECT count(*) n FROM office_tasks WHERE status='working'")['n']
    return {'cleared': len(rows), 'cleared_logs': scope == 'all', 'working': working}

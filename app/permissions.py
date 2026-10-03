"""Owner-controlled access mode. Requeue checkpoints; never invent execution receipts."""
import time
from . import db


def resume_waiting():
    from . import office, project_jobs
    office.init(); project_jobs.init()
    now = time.time(); count = 0
    for table in ('project_jobs', 'office_tasks'):
        rows = db.q("SELECT id,approval_id FROM " + table + " WHERE status='waiting' AND approval_id>0")
        for row in rows:
            approval = db.one('SELECT status FROM approvals WHERE id=?', (row['approval_id'],))
            if not approval or approval['status'] != 'menunggu':
                continue
            # The worker retries the same checkpoint using current source and permissions.
            # Old approval cannot be replayed as an executed or rejected action.
            db.run("UPDATE approvals SET status='diganti' WHERE id=? AND status='menunggu'", (row['approval_id'],))
            db.run("UPDATE " + table + " SET status='queued',approval_id=0,updated_at=? WHERE id=? AND status='waiting'", (now, row['id']))
            if table == 'project_jobs':
                project_jobs.event(row['id'], 'queued', 'Akses penuh diaktifkan pemilik; lanjutkan checkpoint dengan pemeriksaan hasil nyata.')
            count += 1
    return count

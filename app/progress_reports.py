"""Opt-in Telegram progress reports from persisted job/audit state, without LLM calls."""
import asyncio
import hashlib
import json
import time
from . import config,db,telegram


def snapshot():
    jobs=db.q('SELECT id,status,cursor,plan FROM project_jobs ORDER BY id DESC LIMIT 8')
    audit_file=config.WORK_DIR/'audit-github/status.json'
    audit=json.loads(audit_file.read_text()) if audit_file.exists() else {}
    rows=audit.get('repositories',[])
    state={'jobs':jobs,'audit':{'status':audit.get('status'),'count':len(rows),'needs_review':sum(bool(r.get('needs_review')) for r in rows)}}
    fingerprint=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
    active=any(j['status'] in ('queued','working','planning') for j in jobs) or audit.get('status')=='working'
    labels={'queued':'antrean','working':'dikerjakan','planning':'menyusun rencana','paused':'dijeda','failed':'gagal; perlu perbaikan','waiting':'menunggu izin','review':'siap ditinjau','done':'selesai'}
    lines=['**Laporan Agen Mini**']
    if audit:
        lines.append(f"Audit GitHub baca saja: {audit.get('status')} · {len(rows)} repo tercatat · {state['audit']['needs_review']} repo dengan workflow terakhir gagal.")
        lines.append('Repo dalam daftar jangan disentuh dilewati. Audit workflow belum membuktikan seluruh aplikasi berfungsi.')
    for j in jobs:
        plan=json.loads(j['plan'] or '{}');total=len(plan.get('milestones',[]))
        lines.append(f"Proyek #{j['id']}: {labels.get(j['status'],j['status'])} · {j['cursor']}/{total} tahap selesai.")
    if any(j['status']=='paused' for j in jobs):lines.append('Proyek yang dijeda tidak dilanjutkan otomatis. Periksa alasan jeda di Workspace; repo dan salinan lokal dipertahankan.')
    lines.append('Detail: Workspace → Proyek dan Berkas → audit-github/status.json. Laporan berkala setiap 10 menit saat pekerjaan aktif; perubahan status dan hasil akhir juga dilaporkan. /laporan off untuk berhenti.')
    return '\n\n'.join(lines),fingerprint,active

async def emit(force=False):
    if db.setting('progress_reports_enabled')!='1':return None
    destination=db.setting('progress_report_chat')
    if not destination or not telegram.is_allowed(destination,destination):raise ValueError('Tujuan laporan bukan chat Telegram yang diizinkan.')
    token=db.setting('telegram_token')
    if not token:raise ValueError('Bot Telegram utama belum tersambung.')
    text,fingerprint,active=snapshot();now=time.time()
    last=float(db.setting('progress_report_last_at') or 0)
    changed=fingerprint!=db.setting('progress_report_fingerprint')
    interval=max(60,int(db.setting('progress_report_interval') or 600))
    if not force and (now-last<30 or (not changed and (not active or now-last<interval))):return None
    tg=telegram._running.get(token) or telegram.TgBot(token)
    response=await tg.send(destination,text)
    if not response or not response.get('message_id'):raise RuntimeError('Telegram belum mengonfirmasi pengiriman laporan.')
    db.set_setting('progress_report_last_at',str(now));db.set_setting('progress_report_fingerprint',fingerprint)
    db.set_setting('progress_report_message_id',str(response['message_id']))
    db.set_setting('progress_report_error','')
    return response['message_id']

async def loop():
    while True:
        try:await emit()
        except Exception as exc:db.set_setting('progress_report_error',str(exc).replace(db.setting('telegram_token') or 'TOKEN_UNSET','[rahasia]')[:300])
        await asyncio.sleep(30)

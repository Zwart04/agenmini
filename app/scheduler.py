"""Jadwal: pengingat, tugas berulang, perapian malam, dan cadangan database."""
import asyncio
import sqlite3
import time
import traceback
from datetime import datetime

from . import agent, browser, config, db, hub, llm, memory, tools


async def run_job(job: dict):
    bot = db.bot(job["bot_id"])
    if not bot:
        return
    if job["kind"] == "reminder":
        await hub.notify(bot["id"], job["channel"], job["ext_id"], f"Pengingat: {job['text']}")
        result = "terkirim"
    else:
        turn = agent.Turn(bot, job["channel"], job["ext_id"], prio=llm.PRIO_TASK)
        res = await turn.run(f"[Tugas terjadwal #{job['id']}] {job['text']}", save_user=True)
        text = f"Tugas terjadwal #{job['id']}:\n\n{res['text']}"
        await hub.notify(bot["id"], job["channel"], job["ext_id"], text, save=False)
        result = res["text"][:500]
    nxt = tools.next_repeat(job["next_run"], job["repeat"])
    if nxt:
        while nxt <= time.time():  # server sempat mati: lompat ke jadwal berikutnya yang akan datang
            nxt = tools.next_repeat(nxt, job["repeat"])
        db.run("UPDATE jobs SET next_run=?, last_result=? WHERE id=?", (nxt, result, job["id"]))
    else:
        db.run("UPDATE jobs SET active=0, last_result=? WHERE id=?", (result, job["id"]))


def backup_db():
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = config.BACKUP_DIR / f"agen-{datetime.now():%Y%m%d}.sqlite"
    src = db.conn()
    dst = sqlite3.connect(target)
    with db._lock:
        src.backup(dst)
    dst.close()
    olds = sorted(config.BACKUP_DIR.glob("agen-*.sqlite"))
    for old in olds[:-7]:
        old.unlink()


async def nightly():
    try:
        backup_db()
        report = await memory.consolidate()
        db.set_setting("last_consolidate", f"{datetime.now():%d/%m/%Y %H.%M}: {report}")
    except Exception:
        traceback.print_exc()


async def loop():
    running: set[int] = set()
    while True:
        try:
            now = time.time()
            for job in db.q("SELECT * FROM jobs WHERE active=1 AND next_run<=?", (now,)):
                if job["id"] in running:
                    continue
                running.add(job["id"])

                async def _go(j=job):
                    try:
                        await run_job(j)
                    except Exception:
                        traceback.print_exc()
                        db.run("UPDATE jobs SET next_run=? WHERE id=?", (time.time() + 600, j["id"]))
                    finally:
                        running.discard(j["id"])
                asyncio.create_task(_go())
            # perapian malam jam 03.00 (sekali per hari)
            today = datetime.now().strftime("%Y-%m-%d")
            if datetime.now().hour == 3 and db.setting("nightly_done") != today:
                db.set_setting("nightly_done", today)
                asyncio.create_task(nightly())
            await browser.pool.reap()
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(20)

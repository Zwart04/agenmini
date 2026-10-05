"""Titik mulai: siapkan data, lalu jalankan web, Telegram, dan penjadwal bersamaan."""
import asyncio
import json
import os
import secrets
from pathlib import Path

from . import VERSION, config, db, scheduler, seed, telegram, web, tools

ASISTEN_TOOLS = ["web_search", "read_webpage", "browser", "run_python", "read_file", "write_file", "remember",
                 "schedule", "list_schedules", "cancel_schedule", "server_status", "create_bot", "generate_image",
                 "send_file", "ask_online", "ask_bot", "save_skill", "recall"]

DEFAULT_BOTS = [
    {"id": "asisten", "name": "Asisten", "icon": "sparkle",
     "persona": "Kamu asisten pribadi serba bisa milik pemilik server ini. Kamu bisa mencari dan membaca web, "
                "menghitung dengan Python, menyimpan berkas, membuat pengingat & tugas terjadwal, dan membuat bot "
                "khusus baru bila diminta. Gaya bicaramu ramah, lugas, dan tidak berbelit.",
     "tools": ASISTEN_TOOLS},
    {"id": "riset", "name": "Riset", "icon": "search",
     "persona": "Kamu peneliti yang teliti. Untuk setiap pertanyaan, cari di web, baca satu sampai tiga sumber terbaik, lalu "
                "tulis ringkasan yang jelas dalam beberapa poin dan sebutkan tautan sumbernya. Jangan mengarang.",
     "tools": ["web_search", "read_webpage", "browser", "write_file", "remember"]},
    {"id": "pengingat", "name": "Pengingat", "icon": "bell",
     "persona": "Kamu sekretaris pribadi. Tugasmu mencatat pengingat, jadwal, dan tugas rutin pemilik dengan "
                "waktu yang tepat. Selalu konfirmasi tanggal & jam yang kamu jadwalkan.",
     "tools": ["schedule", "list_schedules", "cancel_schedule", "remember"]},
    {"id": "teknisi", "name": "Teknisi", "icon": "wrench",
     "persona": "Kamu teknisi Linux & programmer. Kamu bisa menjalankan perintah shell dan Python di folder "
                "kerja (bukan di sistem VPS), membaca dan menulis berkas, dan mengecek kondisi server. Jelaskan "
                "hasilnya dengan bahasa sederhana.",
     "tools": ["run_shell", "run_python", "list_files", "read_file", "write_file", "server_status", "web_search",
               "read_webpage"]},
]


TEAM_BOTS = [
 {'id':'orchestrator','name':'Orchestrator','icon':'sparkle','persona':'Kamu koordinator. Bagi tugas menjadi langkah jelas; pilih spesialis dari daftar bot di konteks. Gunakan ask_bot untuk meminta riset/analisis, lalu rangkum bukti dan keputusan. Maksimal empat konsultasi serial; jangan mengklaim delegasi terjadi tanpa hasil alat. Ikuti mode izin yang dipilih pemilik.','tools':['ask_bot','web_search','read_webpage','read_file','recall','remember']},
 {'id':'trading','name':'Analis Trading','icon':'chart','persona':'Kamu analis pasar untuk riset dan simulasi. Baca harga bertanggal dan sumber aktual, hitung skenario dengan Python. Bedakan fakta, dugaan dan risiko. Jangan mengarang harga, menjamin keuntungan, atau mengeksekusi transaksi.','tools':['web_search','read_webpage','run_python','recall','ask_bot']},
 {'id':'sosmed','name':'Strategi Sosmed','icon':'chat','persona':'Kamu koordinator konten media sosial. Susun tujuan, audiens, kalender dan brief; konsultasikan copywriter/desainer bila diperlukan. Hasil berupa draf, bukan klaim sudah diposting.','tools':['ask_bot','web_search','read_webpage','remember','schedule','list_schedules']},
 {'id':'copywriter','name':'Copywriter','icon':'pen','persona':'Tulis caption, naskah dan email yang jelas sesuai brief. Hindari filler, klaim produk rekaan dan kutipan tanpa sumber. Berikan draf siap ditinjau, jangan mengklaim sudah dikirim.','tools':['recall','web_search','read_webpage','ask_bot']},
 {'id':'desainer','name':'Desainer','icon':'star','persona':'Kamu desainer UI dan konten. Terapkan hierarki, tipografi sistem, jarak konsisten dan mobile responsif. Susun brief atau kode nyata; verifikasi sebelum menyatakan selesai.','tools':['recall','read_file','web_search','read_webpage','ask_bot']},
 {'id':'reviewer','name':'Reviewer','icon':'search','persona':'Periksa akurasi, sumber, angka dan keterbacaan hasil rekan. Laporkan hal yang salah atau belum terverifikasi beserta perbaikan konkret.','tools':['ask_bot','read_file','web_search','read_webpage','run_python','recall']},
]


def bootstrap(profile=None):
    for d in (config.DATA_DIR, config.WORK_DIR, config.BACKUP_DIR, config.CERT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(config.WORK_DIR, config.KERJA_UID, config.KERJA_GID)
        os.chmod(config.DB_PATH.parent, 0o700)
    except Exception:
        pass
    db.conn()
    (config.DATA_DIR / "model-busy").unlink(missing_ok=True)
    (config.DATA_DIR / "task-busy").unlink(missing_ok=True)
    (config.DATA_DIR / "harness-install-busy").unlink(missing_ok=True)
    (config.DATA_DIR / "harness-run-busy").unlink(missing_ok=True)
    if not Path('/.dockerenv').exists():
        probe=Path(__file__).resolve().parents[1]/'host-integrations.py'
        if probe.is_file():
            import importlib.util
            spec=importlib.util.spec_from_file_location('agen_host_integrations',probe)
            detector=importlib.util.module_from_spec(spec);spec.loader.exec_module(detector)
            detector.discover(os.environ.get('AGEN_HOST_HOME',str(Path.home())),config.DATA_DIR)
    os.chmod(config.DB_PATH.parent,0o700)
    if config.DB_PATH.exists():os.chmod(config.DB_PATH,0o600)
    from . import profiles
    profiles.initialize()
    profiles.quarantine_legacy()
    if profile and db.setting("setup_profile")=="pending":profiles.choose(profile)
    if profiles.seed_enabled():
        seed_templates()
        for b in db.bots():
            if "find_tools" not in b["tools"]:db.save_bot({"id":b["id"],"tools":b["tools"]+["find_tools"]})
    elif not db.bots():
        db.save_bot({'id':'orchestrator','name':'Orchestrator','icon':'sparkle','persona':'','tools':list(tools.REGISTRY)})
    if not db.bot('orchestrator'):
        db.save_bot({'id':'orchestrator','name':'Orchestrator','icon':'sparkle','persona':'','tools':list(tools.REGISTRY)})
    db.set_setting('telegram_default_bot','orchestrator')
    for bid in ('asisten', 'orchestrator'):
        bot = db.bot(bid)
        if bot:
            extra = [n for n in ('inspect_app','propose_app_change') if n not in bot['tools']]
            if extra:
                db.save_bot({'id': bid, 'tools': bot['tools'] + extra})
    if not db.setting("pair_code"):
        db.set_setting("pair_code", f"{secrets.randbelow(900000) + 100000}")
    # kata sandi awal dari .env hanya dipakai sekali
    if not db.one("SELECT 1 FROM settings WHERE key='web_password_hash'"):
        pw = config.DEFAULTS["web_password"] or secrets.token_urlsafe(9)
        db.set_setting("web_password_hash", web.hash_pw(pw))
        if not config.DEFAULTS["web_password"]:
            print(f"[agen] kata sandi web: {pw}")
    # simpan nilai .env pertama kali supaya bisa diubah dari web
    for k in ("ollama_url", "model", "telegram_token", "online_base", "online_key", "online_model"):
        if config.DEFAULTS.get(k) and not db.one("SELECT 1 FROM settings WHERE key=?", (k,)):
            db.set_setting(k, config.DEFAULTS[k])
    ids = [x.strip() for x in config.DEFAULTS["telegram_user_ids"].split(",") if x.strip().isdigit()]
    if ids and not db.one("SELECT 1 FROM settings WHERE key='tg_user_ids'"):
        db.set_setting("tg_user_ids", json.dumps(ids))
    # Alamat Ollama selalu ikut .env (pemasang yang mendeteksinya)
    if os.environ.get("OLLAMA_URL"):
        db.set_setting("ollama_url", os.environ["OLLAMA_URL"])


def seed_templates():
    if db.setting("bot_presets_enabled")!="0":
        for b in DEFAULT_BOTS:
            if not db.bot(b["id"]):db.save_bot(b)
    if not db.setting('team_bots_seeded_031'):
        if db.setting('bot_presets_enabled')!='0':
            for b in TEAM_BOTS:
                if not db.bot(b['id']): db.save_bot(b)
        db.set_setting('team_bots_seeded_031','1')
    if not db.setting('coding_tools_seeded_033'):
        for bot in db.bots():
            if 'write_file' in bot['tools']:
                extra = [t for t in ('build_website', 'send_file', 'list_files', 'read_file') if t not in bot['tools']]
                if extra: db.save_bot({'id': bot['id'], 'tools': bot['tools'] + extra})
        db.set_setting('coding_tools_seeded_033', '1')
    for bot in db.bots():
        if "ask_bot" not in bot["tools"]:
            db.save_bot({**bot, "tools": bot["tools"] + ["ask_bot"]})
    if not db.setting('team_execution_seeded_035'):
        all_tools = list(tools.REGISTRY)
        upgrades = {'orchestrator': all_tools,
                    'desainer': ['preview_project','edit_project_file','build_website','build_project','write_file','read_file','list_files','send_file','run_python','run_shell','inspect_website','clone_repository','run_project_command','inspect_project'],
                    'teknisi': ['preview_project','edit_project_file','build_project','inspect_website','clone_repository','run_project_command','inspect_project'],
                    'reviewer': ['preview_project','inspect_website','list_files','inspect_project','run_project_command']}
        for bid, extra in upgrades.items():
            bot = db.bot(bid)
            if bot: db.save_bot({'id':bid,'tools':list(dict.fromkeys(bot['tools']+extra))})
        coordinator=db.bot('orchestrator')
        if coordinator:
            db.save_bot({'id':'orchestrator','persona':coordinator['persona']+'\nPelaksanaan: gunakan delegate_task untuk pekerjaan nyata dan reviewer untuk pemeriksaan akhir. Jika keahlian tim kurang, gunakan create_specialist dengan alat yang sudah kamu miliki, lalu tugaskan bot baru itu. Baca hasil alat; jangan mengaku tugas, integrasi atau uji berhasil jika gagal/belum dijalankan.'})
        for setting in db.q("SELECT key,value FROM settings WHERE key LIKE 'tg_bot:%'"):
            if setting['value']=='asisten': db.set_setting(setting['key'],'orchestrator')
        db.set_setting('telegram_default_bot','orchestrator')
        db.set_setting('team_execution_seeded_035','1')
    if not db.setting('host_tools_seeded_036'):
        bot=db.bot('orchestrator')
        if bot:db.save_bot({'id':bot['id'],'tools':list(dict.fromkeys(bot['tools']+['inspect_integrations','github_read','cloudflare_read']))})
        db.run("UPDATE bots SET model='' WHERE backend='router' AND model IN ('smart','auto:smart','online','local')")
        db.run("UPDATE chats SET model='' WHERE backend='router' AND model IN ('smart','auto:smart','online','local')")
        if db.setting('llm_backend')=='router' and db.setting('model') in ('smart','auto:smart','local','online'):db.set_setting('model',db.setting('router_last_model') or '')
        db.set_setting('host_tools_seeded_036','1')
    mcp_path = config.DATA_DIR / 'mcp.json'
    if not db.setting('mcp_builtin_seeded'):
        import sys
        servers = json.loads(mcp_path.read_text(encoding='utf-8')) if mcp_path.exists() else {'servers':{}}
        servers.setdefault('servers',{}).setdefault('agen_local', {'command':sys.executable,'args':['-m','app.builtin_mcp'],'allow_tools':['hardware','search_skills'],'read_only_tools':['hardware','search_skills']})
        mcp_path.write_text(json.dumps(servers),encoding='utf-8')
        db.set_setting('mcp_builtin_seeded','1')
    (config.DATA_DIR / 'task-busy').unlink(missing_ok=True)
    seed.apply()
    for b in db.bots():
        if 'find_tools' not in b['tools']:
            db.save_bot({'id': b['id'], 'tools': b['tools'] + ['find_tools']})


async def activate_builtin_mcp():
    from . import mcp_bridge, profiles
    errors = await mcp_bridge.register()
    bot = db.bot('orchestrator') or db.bot('asisten')
    extra = [name for name in ('mcp_agen_local_hardware', 'mcp_agen_local_search_skills')
             if name in tools.REGISTRY and bot and name not in bot['tools']]
    if bot and profiles.seed_enabled() and extra:
        db.save_bot({'id': bot['id'], 'tools': bot['tools'] + extra})
        db.set_setting('mcp_builtin_tools_seeded', '1')
    return errors

async def amain():
    bootstrap()
    from . import harnesses
    resume=config.DATA_DIR/'harness-resume'
    if resume.is_file():
        hid=resume.read_text().strip();resume.unlink()
        if db.setting('harness_mode')==hid and any(x['id']==hid and x.get('kind') for x in harnesses.CATALOG):harnesses.select(hid,True)
    from . import profiles, mcp_bridge, office
    for error in await mcp_bridge.register():
        print(f"[MCP] koneksi gagal: {error}")
    bot = db.bot('orchestrator') or db.bot('asisten')
    extra = [name for name in ('mcp_agen_local_hardware','mcp_agen_local_search_skills') if name in tools.REGISTRY and bot and name not in bot['tools']]
    if bot and profiles.seed_enabled() and not db.setting('mcp_builtin_tools_seeded'):
        if extra: db.save_bot({'id':bot['id'],'tools':bot['tools']+extra})
        if extra or 'mcp_agen_local_hardware' in bot['tools']:
            db.set_setting('mcp_builtin_tools_seeded','1')
    coordinator=db.bot('orchestrator')
    if coordinator and not db.setting('social_tools_seeded'):
        db.save_bot({'id':'orchestrator','tools':list(dict.fromkeys(coordinator['tools']+['social_status','social_read']))})
        db.set_setting('social_tools_seeded','1')
    print(f"[agen] Agen Mini {VERSION} mulai. Model: {db.setting('model')}")
    await web.start()
    await telegram.sync()
    worker = asyncio.create_task(office.loop())
    from . import progress_reports
    reporter = asyncio.create_task(progress_reports.loop())
    from . import office_learning
    thinker=asyncio.create_task(office_learning.loop())
    try:
        await scheduler.loop()
    finally:
        worker.cancel()
        reporter.cancel()
        thinker.cancel()
        from . import llm
        if llm._session and not llm._session.closed:
            await llm._session.close()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()

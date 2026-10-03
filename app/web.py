"""Server web (HTTPS) + API untuk halaman chat & panel."""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import ssl
import subprocess
import time

from aiohttp import web

from . import VERSION, agent, bench, config, db, hub, llm, telegram, tools

COOKIE = "agen_sesi"
_fail: dict[str, list[float]] = {}


def _secret() -> bytes:
    s = db.setting("secret")
    if not s:
        s = secrets.token_hex(32)
        db.set_setting("secret", s)
    return s.encode()


def make_token() -> str:
    exp = str(int(time.time()) + 30 * 86400)
    ver = db.setting("session_ver") or "1"
    sig = hmac.new(_secret(), f"{exp}.{ver}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{ver}.{sig}"


def check_token(tok: str) -> bool:
    try:
        exp, ver, sig = tok.split(".")
        if int(exp) < time.time() or ver != (db.setting("session_ver") or "1"):
            return False
        good = hmac.new(_secret(), f"{exp}.{ver}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(good, sig)
    except Exception:
        return False


def hash_pw(pw: str) -> str:
    salt = secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()


def verify_pw(pw: str) -> bool:
    stored = db.setting("web_password_hash")
    if not stored:
        return False
    salt, h = stored.split("$", 1)
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex(), h)


@web.middleware
async def auth_mw(request: web.Request, handler):
    p = request.path
    if p == "/" or p.startswith("/static/") or p in ("/api/login", "/sehat", "/manifest.json"):
        return await handler(request)
    if not check_token(request.cookies.get(COOKIE, "")):
        return web.json_response({"error": "belum masuk"}, status=401)
    return await handler(request)


async def system_stats() -> dict:
    mem = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":")
            mem[k] = int(v.split()[0]) // 1024
    except Exception:
        pass
    try:
        load = open("/proc/loadavg").read().split()[:3]
    except Exception:
        load = ["?"]
    du = shutil.disk_usage(str(config.DATA_DIR))
    loaded, installed = [], []
    try:
        if db.setting("llm_backend") != "ollama" or db.setting("model") == "online":
            raise RuntimeError("Ollama tidak dipakai")
        ps = await llm.ollama_get("/api/ps")
        loaded = [f"{m['name']} ({round(m.get('size', 0) / 1e9, 1)} GB)" for m in ps.get("models", [])]
        tags = await llm.ollama_get("/api/tags")
        installed = [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 2)} for m in tags.get("models", [])]
        ollama_ok = True
    except Exception:
        ollama_ok = False
    agent_mb = 0
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS"):
                agent_mb = int(line.split()[1]) // 1024
    except Exception:
        pass
    from . import runtime_status, local_models
    runtime = await runtime_status.state() if db.setting('llm_backend') == 'local' else {}
    hw = local_models.hardware()
    if hw.get('source') == 'host':
        mem['MemTotal'] = hw['ram_mb']; mem['MemAvailable'] = hw['available_mb']
    local_name = next((m['name'] for m in local_models.all_models() if m['id'] == db.setting('local_model_id')), 'Model lokal')
    return {
        "version": VERSION, "backend": db.setting("llm_backend"), "runtime":runtime, "local_model_name":local_name,
        "ram_total_mb": mem.get("MemTotal", 0), "ram_available_mb": mem.get("MemAvailable", 0),
        "ram_used_mb": mem.get("MemTotal", 0) - mem.get("MemAvailable", 0),
        "swap_used_mb": mem.get("SwapTotal", 0) - mem.get("SwapFree", 0), "swap_total_mb": mem.get("SwapTotal", 0),
        "agent_mb": agent_mb, "load": " ".join(load), "cpus": os.cpu_count(),
        "disk_free_gb": round(du.free / 1e9, 1),
        "model": db.setting("model"), "active_model": llm.default_model(), "loaded": loaded, "installed": installed, "ollama_ok": ollama_ok,
        "queue": llm.gate.waiting() + (1 if llm.gate.busy else 0), "busy_model": llm.gate.current,
        "telegram": telegram.status(), "online": llm.online_ready(),
        "last_consolidate": db.setting("last_consolidate"),
    }


# ---------- rute ----------

routes = web.RouteTableDef()


@routes.get("/")
async def index(request):
    return web.FileResponse(config.STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/sehat")
async def health(request):
    return web.json_response({"ok": True})


@routes.post("/api/login")
async def login(request):
    ip = request.headers.get("X-Forwarded-For", request.remote or "?")
    now = time.time()
    tries = [t for t in _fail.get(ip, []) if now - t < 600]
    if len(tries) >= 8:
        return web.json_response({"error": "Terlalu banyak percobaan. Tunggu 10 menit."}, status=429)
    data = await request.json()
    if not verify_pw(data.get("password", "")):
        tries.append(now)
        _fail[ip] = tries
        await asyncio.sleep(1)
        return web.json_response({"error": "Kata sandi salah."}, status=401)
    _fail.pop(ip, None)
    resp = web.json_response({"ok": True})
    resp.set_cookie(COOKIE, make_token(), max_age=30 * 86400, httponly=True, secure=request.secure, samesite="Strict")
    return resp


@routes.post("/api/logout")
async def logout(request):
    resp = web.json_response({"ok": True})
    resp.del_cookie(COOKIE)
    return resp


@routes.get("/api/me")
async def me(request):
    return web.json_response({"ok": True, "version": VERSION})


# bot

@routes.get("/api/bots")
async def list_bots(request):
    rows = db.bots()
    for r in rows:
        r["telegram_token"] = "••••" + r["telegram_token"][-4:] if r["telegram_token"] else ""
        r["skills"] = db.one("SELECT COUNT(*) n FROM skills WHERE scope=? AND active=1", (r["id"],))["n"]
    return web.json_response({"bots": rows, "tools": [{"name": t.name, "label": t.label, "description": t.description}
                                                      for t in tools.REGISTRY.values()]})


@routes.post("/api/bots")
async def save_bot(request):
    data = await request.json()
    if data.get("backend", "") not in ("", "auto", "router", "freellmapi", "online", "local"):
        return web.json_response({"error":"Mesin bot tidak dikenal."}, status=400)
    backend=data.get('backend', '')
    selected=str(data.get('model', '')).strip()
    if selected and backend in ('router', 'freellmapi', 'auto'):
        from . import router, free_router
        rows=[{'id':'smart'}] if backend=='auto' else (await router.state())['models'] if backend=='router' else await free_router.models()
        if selected not in [m['id'] for m in rows]:
            return web.json_response({'error':'ID model tidak tersedia. Hubungkan provider di Koneksi dan pilih model dari daftar.'}, status=400)
    if selected and backend=='local' and selected != db.setting('local_model_id'):
        return web.json_response({'error':'Bot lokal berbagi satu model aktif. Ganti model di Koneksi.'}, status=400)
    if not data.get("name"):
        return web.json_response({"error": "Nama wajib diisi."}, status=400)
    if str(data.get("telegram_token", "")).startswith("••••"):
        data.pop("telegram_token")
    data["tools"] = [t for t in data.get("tools", []) if t in tools.REGISTRY]
    bid = db.save_bot(data)
    await telegram.sync()
    from . import runtime_status
    if not (config.DATA_DIR / "runtime-request").exists() and not (config.DATA_DIR / "runtime-processing").exists():
        runtime_status.request("reconcile")
    return web.json_response({"id": bid})


@routes.delete("/api/bots/{id}")
async def delete_bot(request):
    bid = request.match_info["id"]
    if len(db.bots()) <= 1:
        return web.json_response({"error": "Minimal harus ada satu bot."}, status=400)
    db.run("DELETE FROM bots WHERE id=?", (bid,))
    db.run("UPDATE jobs SET active=0 WHERE bot_id=?", (bid,))
    await telegram.sync()
    return web.json_response({"ok": True})


# chat

def web_ext() -> str:
    return "web"


@routes.get("/api/chat/{bot}")
async def chat_history(request):
    bot = db.bot(request.match_info["bot"])
    if not bot:
        return web.json_response({"error": "bot tidak ada"}, status=404)
    cid = request.query.get("chat_id")
    chat = db.one("SELECT * FROM chats WHERE id=? AND bot_id=?", (int(cid), bot["id"])) if cid else None
    chat = chat or db.chat_for(bot["id"], "web", web_ext())
    rows = db.q("SELECT id, role, content, meta, created_at, feedback FROM messages WHERE chat_id=? "
                "AND role IN ('user','assistant') ORDER BY id DESC LIMIT 200", (chat["id"],))
    rows.reverse()
    for r in rows:
        r["meta"] = json.loads(r["meta"] or "{}")
    return web.json_response({"messages": rows, "chat": {k: chat[k] for k in ("id", "title", "channel", "archived", "backend", "model")}})


# ---------- riwayat percakapan ----------

@routes.get("/api/chats")
async def chats_list(request):
    bot_id = request.query.get("bot", "")
    rows = db.q("SELECT c.id, c.bot_id, c.channel, c.title, c.archived, c.created_at, c.updated_at, "
                "(SELECT COUNT(*) FROM messages m WHERE m.chat_id=c.id) n FROM chats c "
                "WHERE (?='' OR c.bot_id=?) ORDER BY c.updated_at DESC LIMIT 300", (bot_id, bot_id))
    return web.json_response({"chats": [r for r in rows if r["n"]]})


@routes.post("/api/chats/{id}/buka")
async def chat_open(request):
    ch = db.one("SELECT * FROM chats WHERE id=?", (int(request.match_info["id"]),))
    if not ch:
        return web.json_response({"error": "percakapan tidak ada"}, status=404)
    if ch["channel"] != "web":
        return web.json_response({"error": "Percakapan Telegram dilanjutkan dari Telegram (/riwayat)."}, status=400)
    db.open_chat(ch["id"])
    return web.json_response({"ok": True})


@routes.post("/api/chats/{id}")
async def chat_rename(request):
    data = await request.json()
    title = " ".join(str(data.get("title", "")).split())[:80]
    if title:
        db.run("UPDATE chats SET title=? WHERE id=?", (title, int(request.match_info["id"])))
    return web.json_response({"ok": True})


@routes.post('/api/chats/{id}/salin')
async def chat_copy(request):
    chat = db.copy_chat(int(request.match_info['id']), 'web', web_ext())
    return web.json_response({'id': chat['id'], 'bot': chat['bot_id']})


@routes.delete("/api/chats/{id}")
async def chat_delete(request):
    db.delete_chat(int(request.match_info["id"]))
    return web.json_response({"ok": True})


@routes.get("/api/chats/{id}/unduh")
async def chat_download(request):
    cid = int(request.match_info["id"])
    ch = db.one("SELECT title FROM chats WHERE id=?", (cid,))
    if not ch:
        return web.json_response({"error": "percakapan tidak ada"}, status=404)
    name = re.sub(r"[^\w]+", "", (ch["title"] or "percakapan").lower())[:40] or "percakapan"
    return web.Response(text=db.export_chat(cid), content_type="text/markdown", charset="utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.md"'})


@routes.get("/api/files")
async def serve_file(request):
    """Berkas dari folder kerja (gambar unggahan, gambar buatan, grafik) untuk ditampilkan di chat."""
    from . import vision
    try:
        path = vision.work_path(request.query.get("path", ""))
    except ValueError:
        return web.json_response({"error": "tidak boleh"}, status=403)
    if not path.is_file():
        return web.json_response({"error": "berkas tidak ada"}, status=404)
    headers = {"Cache-Control": "private, max-age=86400"}
    if path.suffix.lower() in ('.html', '.htm', '.js', '.svg'):
        from urllib.parse import quote
        filename = path.name
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
        headers['Content-Disposition'] = f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(filename, safe='')}"
    return web.FileResponse(path, headers=headers)


async def _stream(request, runner):
    resp = web.StreamResponse(headers={"Content-Type": "application/x-ndjson", "Cache-Control": "no-cache",
                                       "X-Accel-Buffering": "no"})
    await resp.prepare(request)
    q: asyncio.Queue = asyncio.Queue()

    async def on_event(kind, data):
        await q.put({"type": kind, "data": data})

    task = asyncio.create_task(runner(on_event))
    try:
        while True:
            get = asyncio.create_task(q.get())
            done, _ = await asyncio.wait({get, task}, timeout=15, return_when=asyncio.FIRST_COMPLETED)
            if get in done:
                ev = get.result()
                await resp.write((json.dumps(ev, ensure_ascii=False) + "\n").encode())
                if ev["type"] == "done":
                    break
            else:
                get.cancel()
                if task in done:
                    exc = task.exception()
                    if exc:
                        await resp.write((json.dumps({"type": "done", "data": {"text": f"Galat: {exc}"}}) + "\n").encode())
                    break
                await resp.write(b'{"type":"ping"}\n')
    except (ConnectionResetError, asyncio.CancelledError):
        pass  # pengguna menutup halaman; agen tetap menyelesaikan & menyimpan jawabannya
    return resp


@routes.post("/api/chat/{bot}")
async def chat_send(request):
    bot = db.bot(request.match_info["bot"])
    data = await request.json()
    text = (data.get("text") or "").strip()
    images = []
    for item in (data.get("images") or [])[:3]:
        try:
            raw = base64.b64decode(str(item).split(",", 1)[-1])
        except Exception:
            continue
        from . import vision
        if vision.is_image_bytes(raw):
            images.append(raw)
    if not bot or (not text and not images):
        return web.json_response({"error": "pesan kosong"}, status=400)
    if data.get("chat_id"):  # lanjutkan percakapan web dari riwayat
        ch = db.one("SELECT * FROM chats WHERE id=? AND bot_id=? AND channel='web'", (int(data["chat_id"]), bot["id"]))
        if ch and ch["archived"]:
            db.open_chat(ch["id"])
    return await _stream(request, lambda ev: agent.Turn(bot, "web", web_ext(), ev).run(text, images=images or None))


@routes.post("/api/chat/{bot}/reset")
async def chat_reset(request):
    db.new_chat(request.match_info["bot"], "web", web_ext())
    return web.json_response({"ok": True})


@routes.post("/api/approval/{id}")
async def approval(request):
    data = await request.json()
    aid = int(request.match_info["id"])
    return await _stream(request, lambda ev: agent.resolve_approval(aid, bool(data.get("ok")), ev))


@routes.post("/api/feedback")
async def feedback(request):
    data = await request.json()
    await agent.feedback(int(data["message_id"]), bool(data.get("good")), data.get("note", ""))
    return web.json_response({"ok": True})


@routes.get("/api/events")
async def events(request):
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                       "X-Accel-Buffering": "no"})
    await resp.prepare(request)
    q: asyncio.Queue = asyncio.Queue()
    hub.web_listeners.add(q)
    try:
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), 25)
                await resp.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        hub.web_listeners.discard(q)
    return resp


# memori, skill, jadwal

@routes.get("/api/memories")
async def memories(request):
    qtext = request.query.get("q", "").strip()
    if qtext:
        from .memory import fts_query
        fq = fts_query(qtext)
        rows = db.q("SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.rowid WHERE memories_fts MATCH ? "
                    "ORDER BY bm25(memories_fts) LIMIT 100", (fq,)) if fq else []
    else:
        rows = db.q("SELECT * FROM memories ORDER BY id DESC LIMIT 300")
    return web.json_response({"memories": rows})


@routes.post("/api/memories")
async def add_memory(request):
    from .memory import add_memory as add
    data = await request.json()
    mid, new = add(data.get("scope") or "shared", data.get("kind") or "fakta", data.get("text", ""))
    return web.json_response({"id": mid, "new": new})


@routes.delete("/api/memories/{id}")
async def del_memory(request):
    db.run("DELETE FROM memories WHERE id=?", (int(request.match_info["id"]),))
    return web.json_response({"ok": True})


@routes.get("/api/skills")
async def skills(request):
    return web.json_response({"skills": db.q("SELECT * FROM skills ORDER BY active DESC, updated_at DESC")})


@routes.post("/api/skills/{id}")
async def update_skill(request):
    data = await request.json()
    sid = int(request.match_info["id"])
    if "active" in data:
        db.run("UPDATE skills SET active=? WHERE id=?", (int(bool(data["active"])), sid))
    if "steps" in data:
        db.run("UPDATE skills SET steps=?, when_to_use=?, name=?, updated_at=? WHERE id=?",
               (data["steps"], data.get("when_to_use", ""), data.get("name", ""), time.time(), sid))
    if "scope" in data:
        scope = data["scope"]
        if scope != "shared" and not db.bot(scope):
            raise web.HTTPBadRequest(text="Bot tidak ditemukan")
        db.run("UPDATE skills SET scope=? WHERE id=?", (scope, sid))
    return web.json_response({"ok": True})


@routes.delete("/api/skills/{id}")
async def del_skill(request):
    db.run("DELETE FROM skills WHERE id=?", (int(request.match_info["id"]),))
    return web.json_response({"ok": True})


@routes.get("/api/jobs")
async def jobs(request):
    return web.json_response({"jobs": db.q("SELECT * FROM jobs WHERE active=1 ORDER BY next_run")})


@routes.delete("/api/jobs/{id}")
async def del_job(request):
    db.run("UPDATE jobs SET active=0 WHERE id=?", (int(request.match_info["id"]),))
    return web.json_response({"ok": True})


# status, model, uji

@routes.get("/api/status")
async def status(request):
    return web.json_response(await system_stats())


@routes.post("/api/models/pull")
async def pull_model(request):
    data = await request.json()
    name = (data.get("name") or "").strip()

    async def runner(ev):
        last = 0.0
        try:
            async for st, pct in llm.pull(name):
                if time.time() - last > 1 or st == "success":
                    last = time.time()
                    await ev("status", f"{st} {pct}%" if pct is not None else st)
            await ev("done", {"text": f"Model {name} siap."})
        except Exception as e:
            await ev("done", {"text": f"Gagal mengunduh: {e}"})
    return await _stream(request, runner)


@routes.post("/api/models/delete")
async def delete_model(request):
    data = await request.json()
    base = db.setting("ollama_url").rstrip("/")
    async with llm.session().delete(f"{base}/api/delete", json={"model": data["name"]}) as r:
        ok = r.status == 200
    return web.json_response({"ok": ok})


@routes.get("/api/bench")
async def bench_get(request):
    return web.json_response({"running": bench.state, "results": db.q("SELECT * FROM bench ORDER BY id DESC LIMIT 60")})


@routes.post("/api/bench")
async def bench_start(request):
    data = await request.json()
    models = [m for m in data.get("models", []) if m]
    if bench.state.get("running"):
        return web.json_response({"error": "Uji masih berjalan."}, status=409)
    asyncio.create_task(bench.run_many(models))
    return web.json_response({"ok": True})


# pengaturan

PUBLIC_SETTINGS = ["llm_backend", "compatible_base", "tool_mode", "model", "num_ctx", "keep_alive", "online_base", "online_model", "searx_url", "max_steps",
                   "browser_engine", "dns_aman", "vision_model", "image_gen", "cpu_hemat", "auto_local", "auto_9router"]


@routes.get("/api/settings")
async def get_settings(request):
    s = {k: db.setting(k) for k in PUBLIC_SETTINGS}
    s["telegram_token"] = ("••••" + db.setting("telegram_token")[-4:]) if db.setting("telegram_token") else ""
    s["compatible_key"] = "••••" if db.setting("compatible_key") else ""
    s["online_key"] = "••••" if db.setting("online_key") else ""
    s["pair_code"] = db.setting("pair_code")
    s["tg_allowed"] = json.loads(db.setting("tg_allowed") or "[]")
    s["tg_user_ids"] = json.loads(db.setting("tg_user_ids") or "[]")
    return web.json_response(s)


@routes.post("/api/settings")
async def set_settings(request):
    data = await request.json()
    if 'llm_backend' in data and data['llm_backend'] != db.setting('llm_backend'):
        return web.json_response({'error': 'Ganti mesin melalui menu AI agar layanan VPS ikut disesuaikan.'}, status=400)
    for k in PUBLIC_SETTINGS:
        if k in data:
            db.set_setting(k, str(data[k]).strip())
    for k in ("telegram_token", "online_key", "compatible_key"):
        if k in data and not str(data[k]).startswith("••••"):
            db.set_setting(k, str(data[k]).strip())
    if "tg_allowed" in data:
        db.set_setting("tg_allowed", json.dumps([str(x) for x in data["tg_allowed"]]))
    if "tg_user_ids" in data:
        ids = [str(x).strip() for x in data["tg_user_ids"] if str(x).strip()]
        if any(not x.isdigit() for x in ids):
            return web.json_response({"error": "User ID Telegram hanya berisi angka (lihat di @userinfobot)."}, status=400)
        db.set_setting("tg_user_ids", json.dumps(ids))
    if data.get("new_password"):
        if len(data["new_password"]) < 8:
            return web.json_response({"error": "Kata sandi minimal 8 karakter."}, status=400)
        db.set_setting("web_password_hash", hash_pw(data["new_password"]))
        db.set_setting("session_ver", str(int(db.setting("session_ver") or "1") + 1))
    if "dns_aman" in data:  # sesi HTTP dibuat ulang supaya pilihan DNS langsung berlaku
        old = llm._session
        llm._session = None
        if old and not old.closed:
            asyncio.get_running_loop().call_later(60, lambda: asyncio.ensure_future(old.close()))
    await telegram.sync()
    return web.json_response({"ok": True})


# ---------- server ----------

def ensure_cert() -> ssl.SSLContext:
    config.CERT_DIR.mkdir(parents=True, exist_ok=True)
    crt, key = config.CERT_DIR / "agen.crt", config.CERT_DIR / "agen.key"
    if not crt.exists() or not key.exists():
        ip = os.environ.get("PUBLIC_IP", "127.0.0.1")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
                        "-keyout", str(key), "-out", str(crt), "-subj", "/CN=agenmini",
                        "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost"],
                       check=True, capture_output=True)
        os.chmod(key, 0o600)
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(str(crt), str(key))
    return ctx


async def start():
    from . import control, native_apps
    app = web.Application(middlewares=[control.errors, auth_mw], client_max_size=16 * 1024 * 1024)  # unggahan gambar
    app.add_routes(control.routes)
    app.add_routes(native_apps.routes)
    app.add_routes(routes)
    app.router.add_static("/static/", config.STATIC_DIR)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    use_tls = os.environ.get("WEB_TLS", "1") != "0"
    site = web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT, ssl_context=ensure_cert() if use_tls else None)
    await site.start()
    print(f"[web] siap di port {config.WEB_PORT} ({'https' if use_tls else 'http'})")

"""Alat-alat agen. Tiap bot hanya diberi sebagian (makin sedikit alat, makin jarang model kecil salah pilih).

Perintah shell/Python dijalankan sebagai user 'kerja' di /data/ruang-kerja: tidak bisa menyentuh database
agen maupun sistem VPS. Perintah yang tampak merusak tetap menunggu izin pemilik.
"""
import asyncio
import json
import os
import re
try:
    import resource
except ImportError:
    resource = None
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import browser, config, db, llm, memory


@dataclass
class Ctx:
    bot: dict
    chat: dict
    channel: str
    ext_id: str
    skills_used: list = field(default_factory=list)
    user_text: str = ""
    attachments: list = field(default_factory=list)  # berkas (jalur relatif folder kerja) yang ikut dikirim


@dataclass
class Tool:
    name: str
    label: str          # nama ramah untuk layar
    description: str
    params: dict
    required: list
    fn: object
    danger: object = None  # fungsi(args) -> alasan (str) kalau butuh izin

    input_schema: dict | None = None

    def schema(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.input_schema or {"type": "object", "properties": self.params, "required": self.required, "additionalProperties": False}}}


REGISTRY: dict[str, Tool] = {}
BOT_ICONS = ["bot", "sparkle", "search", "bell", "wrench", "globe", "chart", "book", "code", "heart", "cart",
             "briefcase", "pen", "calendar", "star", "chat"]


def tool(name, label, description, params, required=(), danger=None):
    def deco(fn):
        REGISTRY[name] = Tool(name, label, description, params, list(required), fn, danger)
        return fn
    return deco


def S(desc):
    return {"type": "string", "description": desc}


def I(desc):
    return {"type": "integer", "description": desc}


def schemas_for(bot: dict) -> list[dict]:
    names = [n for n in bot.get("tools", []) if n in REGISTRY]
    if "ask_online" in names and not llm.online_ready():
        names.remove("ask_online")
    return [REGISTRY[n].schema() for n in names]


def validate_arguments(name, args):
    t = REGISTRY.get(name)
    if not t:
        return "Alat tidak tersedia"
    if not isinstance(args, dict):
        return "Argumen harus objek JSON lengkap"
    import jsonschema
    try:
        jsonschema.validate(args, t.schema()["function"]["parameters"])
    except jsonschema.ValidationError as e:
        return e.message
    for key in t.required:
        if isinstance(args.get(key), str) and not args[key].strip():
            return f"{key} tidak boleh kosong"
    return None


def _kerja_limits():
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    os.setsid()


async def _run_sandboxed(argv: list[str], timeout: int = 60, stdin: bytes | None = None) -> str:
    if os.name != "posix":
        return "Error: eksekusi terisolasi membutuhkan Linux/WSL atau Docker."
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    extra = {}
    if os.geteuid() == 0:
        extra = {"user": config.KERJA_UID, "group": config.KERJA_GID, "extra_groups": []}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(config.WORK_DIR), "LANG": "C.UTF-8",
           "TZ": config.TZ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}  # grafik matplotlib ke berkas
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.PIPE if stdin else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        cwd=str(config.WORK_DIR), env=env, preexec_fn=_kerja_limits, **extra)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(stdin), timeout)
    except asyncio.TimeoutError:
        try:
            os.killpg(proc.pid, 9)
        except Exception:
            proc.kill()
        return f"(dihentikan: lebih dari {timeout} detik)"
    text = out.decode("utf-8", errors="replace").strip()
    if len(text) > 4000:
        text = text[:2000] + "\n…(dipotong)…\n" + text[-1500:]
    return f"[kode keluar {proc.returncode}]\n{text or '(tanpa keluaran)'}"


def _workpath(p: str) -> Path:
    base = config.WORK_DIR.resolve()
    path = (base / (p or ".").lstrip("/")).resolve()
    if base != path and base not in path.parents:
        raise ValueError("Hanya boleh di dalam folder ruang kerja.")
    return path


# ---------- web ----------

@tool("web_search", "Mencari di web",
      "Search the internet for current information. Returns titles, links and snippets.",
      {"query": S("search keywords")}, ["query"])
async def web_search(ctx: Ctx, query: str = "", **_):
    res = await browser.search(query)
    if not res:
        return "Tidak ada hasil."
    out = "\n\n".join(f"{i + 1}. {r['title']}\n{r['url']}\n{r['snippet'][:300]}" for i, r in enumerate(res))
    # Sekalian baca bagian relevan dari sumber teratas: menghemat satu putaran model (15-30 detik di CPU).
    for r in res[:2]:
        if r["url"].lower().endswith(".pdf"):
            continue
        try:
            page = await asyncio.wait_for(browser.read_page(r["url"], query, limit=1800, plain_only=True), 12)
            if len(page["text"]) > 200:
                out += f"\n\nIsi sumber teratas ({page['url']}):\n{page['text']}"
                break
        except Exception:
            continue
    return out


@tool("read_webpage", "Membaca halaman",
      "Open a web page URL and return its main text. Give 'question' to get only the relevant parts.",
      {"url": S("full URL"), "question": S("what you want to find on the page (optional)")}, ["url"])
async def read_webpage(ctx: Ctx, url: str = "", question: str = "", **_):
    r = await browser.read_page(url, question)
    return f"[{r['url']} via {r['via']}]\n{r['text']}"


@tool("browser", "Memakai browser",
      "Interactive browser for pages that need clicking or filling forms. actions: open (needs url), "
      "click (needs target number), type (target + text), submit (target), read, back, close.",
      {"action": S("open | click | type | submit | read | back | close"), "url": S("URL for open"),
       "target": I("element number from the list"), "text": S("text to type")}, ["action"])
async def browser_tool(ctx: Ctx, action: str = "open", url: str = "", target=None, text: str = "", **_):
    try:
        target = int(target) if target not in (None, "") else None
    except (TypeError, ValueError):
        target = None
    return await browser.browse(f"{ctx.chat['id']}", action, url, target, text)


# ---------- eksekusi ----------

DANGER_SHELL = re.compile(
    r"\brm\s+-[a-z]*[rf]|\bmkfs|\bdd\s+if=|\bshutdown|\breboot|\bkill(all)?\b|\bchmod\s+-R|\bchown\s+-R|"
    r"curl[^|]*\|\s*(ba)?sh|wget[^|]*\|\s*(ba)?sh|\bpip3?\s+install|\bapt(-get)?\s|>\s*/(etc|usr|bin|dev)|"
    r"\bnc\s+-l|\bcrontab\b|\bssh\b|\bscp\b", re.I)
DANGER_PY = re.compile(r"shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir|os\.system|subprocess|socket\.|"
                       r"\.unlink\(|smtplib|ctypes|__import__\(", re.I)


@tool("run_python", "Menjalankan Python",
      "Run a short Python 3 script for calculations, data processing or charts (matplotlib, Pillow available; "
      "save charts with plt.savefig('grafik.png') then use send_file). Use print() to show results.",
      {"code": S("python code")}, ["code"],
      danger=lambda a: "kode Python ini bisa menghapus/menjalankan program lain" if DANGER_PY.search(a.get("code", "")) else None)
async def run_python(ctx: Ctx, code: str = "", **_):
    t0 = time.time()
    out = await _run_sandboxed(["python3", "-I", "-"], timeout=60, stdin=code.encode())
    return out + _attach_new_files(ctx, t0)


AUTO_SEND = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf")


def _attach_new_files(ctx: Ctx, since: float) -> str:
    """Grafik/gambar/PDF yang baru dibuat perintah ikut terkirim otomatis (model kecil sering lupa send_file)."""
    base = config.WORK_DIR.resolve()
    new = []
    if base.exists():
        for p in base.rglob("*"):
            rel = str(p.relative_to(base)).replace("\\", "/")
            if (p.is_file() and p.suffix.lower() in AUTO_SEND and p.stat().st_mtime >= since - 1
                    and not rel.startswith(("unggahan/", ".")) and rel not in ctx.attachments):
                new.append(rel)
    ctx.attachments.extend(new[:5])
    return f"\n[Berkas baru, otomatis dikirim ke pengguna: {', '.join(new[:5])}]" if new else ""


@tool("run_shell", "Menjalankan perintah",
      "Run a Linux shell command inside the agent's sandbox folder (not the host server).",
      {"command": S("bash command")}, ["command"],
      danger=lambda a: "perintah ini bisa menghapus/mengubah sistem" if DANGER_SHELL.search(a.get("command", "")) else None)
async def run_shell(ctx: Ctx, command: str = "", **_):
    t0 = time.time()
    out = await _run_sandboxed(["bash", "-lc", command], timeout=90)
    return out + _attach_new_files(ctx, t0)


# ---------- berkas ----------

@tool("list_files", "Melihat berkas", "List files in the workspace folder.", {"path": S("sub-folder, default '.'")})
async def list_files(ctx: Ctx, path: str = ".", **_):
    p = _workpath(path)
    if not p.exists():
        return "Folder tidak ada."
    items = sorted(p.iterdir())[:200]
    return "\n".join(f"{i.name}/" if i.is_dir() else f"{i.name} ({i.stat().st_size} B)"
                     for i in items if not i.name.startswith(".")) or "(kosong)"


@tool("read_file", "Membaca berkas", "Read a text file from the workspace.", {"path": S("file path")}, ["path"])
async def read_file(ctx: Ctx, path: str = "", **_):
    p = _workpath(path)
    if not p.is_file():
        return "Berkas tidak ada."
    t = p.read_text(encoding="utf-8", errors="replace")
    return t[:8000] + ("\n…(dipotong)" if len(t) > 8000 else "")


@tool("write_file", "Menulis berkas", "Write (overwrite) a text file in the workspace.",
      {"path": S("file path"), "content": S("text to write")}, ["path", "content"])
async def write_file(ctx: Ctx, path: str = "", content: str = "", **_):
    p = _workpath(path)
    missing = []
    parent = p.parent
    while not parent.exists():
        missing.append(parent); parent = parent.parent
    p.parent.mkdir(parents=True, exist_ok=True)
    # Newly created subfolders must also be writable by the isolated coding user.
    for folder in missing:
        try: os.chown(folder, config.KERJA_UID, config.KERJA_GID)
        except (OSError, AttributeError): pass
    p.write_text(content, encoding='utf-8')
    try:
        os.chown(p, config.KERJA_UID, config.KERJA_GID)
    except Exception:
        pass
    rel = str(p.relative_to(config.WORK_DIR.resolve())).replace('\\', '/')
    if rel not in ctx.attachments: ctx.attachments.append(rel)
    return f"Tersimpan dan otomatis dikirim: {rel} ({len(content)} karakter)"


@tool('build_website', 'Membuat landing page',
      'Create and verify a complete responsive HTML landing page from a short brief. Automatically sends the file. No deployment or AI backend.',
      {'brief': S('website requirements, product name and audience')}, ['brief'])
async def build_website(ctx: Ctx, brief: str = '', on_token=None, **_):
    from . import coding, office
    office.phase('Menulis HTML dan CSS…', 'writing')
    html, stats = await coding.generate(brief, ctx.bot.get('model') or llm.default_model(), on_token=on_token)
    office.phase('Memeriksa dan menyimpan halaman…', 'tool')
    path = 'website-' + str(time.time_ns()) + '/index.html'
    await write_file(ctx, path, html)
    saved = _workpath(path)
    if saved.read_text(encoding='utf-8') != html: return 'Error: verifikasi berkas gagal.'
    return f'Landing page HTML lengkap terverifikasi dan otomatis dikirim: {path}. Belum dipublikasikan; fitur AI/pembayaran membutuhkan backend nyata.'


# ---------- gambar & kiriman berkas ----------

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


@tool("send_file", "Mengirim berkas",
      "Send a file from the workspace to the user (image, PDF, text, CSV...). Use after creating or saving a file.",
      {"path": S("file path in the workspace"), "caption": S("short caption (optional)")}, ["path"])
async def send_file(ctx: Ctx, path: str = "", caption: str = "", **_):
    p = _workpath(path)
    if not p.is_file():
        return f"Error: berkas '{path}' tidak ada. Buat dulu berkasnya, jangan mengaku sudah membuatnya."
    if p.stat().st_size > 45_000_000:
        return "Error: berkas lebih dari 45 MB, terlalu besar untuk dikirim."
    rel = str(p.relative_to(config.WORK_DIR.resolve())).replace("\\", "/")
    if rel not in ctx.attachments:
        ctx.attachments.append(rel)
    return f"Berkas {rel} akan dikirim bersama jawabanmu."


@tool("generate_image", "Membuat gambar",
      "Create a new picture from a text description (illustration, poster idea, logo idea, photo-like image). "
      "Write the prompt in detailed English. The image is sent to the user automatically.",
      {"prompt": S("detailed English description of the picture"),
       "shape": S("square | portrait | landscape")}, ["prompt"])
async def generate_image(ctx: Ctx, prompt: str = "", shape: str = "square", **_):
    import random
    from urllib.parse import quote
    import aiohttp
    if db.setting("image_gen") == "0":
        return "Error: fitur membuat gambar dimatikan di Pengaturan. Katakan itu ke pengguna."
    w, h = {"portrait": (768, 1152), "landscape": (1152, 768)}.get(shape, (1024, 1024))
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt[:900])}?width={w}&height={h}"
           f"&nologo=true&seed={random.randint(1, 10**9)}")
    data = b""
    for attempt in range(3):
        try:
            async with llm.session().get(url, timeout=aiohttp.ClientTimeout(total=150)) as r:
                if r.status == 429:
                    await asyncio.sleep(16)  # batas gratis: sekitar 1 gambar per 15 detik
                    continue
                data = await r.read()
                if r.status == 200 and r.headers.get("Content-Type", "").startswith("image/"):
                    break
                data = b""
        except Exception:
            await asyncio.sleep(3)
    if not data:
        return "Error: layanan pembuat gambar (Pollinations) sedang tidak bisa dihubungi. Katakan itu ke pengguna."
    folder = config.WORK_DIR / "gambar"
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "", prompt.lower())[:24] or "gambar"
    path = folder / f"{slug}{int(time.time())}.jpg"
    path.write_bytes(data)
    for x in (folder, path):
        try:
            os.chown(x, config.KERJA_UID, config.KERJA_GID)
        except Exception:
            pass
    rel = f"gambar/{path.name}"
    ctx.attachments.append(rel)
    return (f"Gambar berhasil dibuat ({rel}) dan otomatis dikirim ke pengguna. Dibuat oleh layanan Pollinations di "
            f"internet. Kamu TIDAK bisa melihat hasilnya dan hasilnya bisa berbeda dari permintaan, jadi jangan "
            f"menggambarkan isinya. Cukup jawab singkat bahwa gambarnya sudah dikirim dan tawarkan membuat ulang bila "
            f"kurang pas.")


# ---------- memori & skill ----------

@tool("remember", "Mengingat",
      "Save a durable fact to long-term memory (about the user, their preferences, or important info).",
      {"fact": S("the fact, one sentence"), "kind": S("profil | fakta | pelajaran")}, ["fact"])
async def remember(ctx: Ctx, fact: str = "", kind: str = "fakta", **_):
    kind = kind if kind in ("profil", "fakta", "pelajaran") else "fakta"
    if ctx.user_text and not memory.grounded(fact, ctx.user_text, need=0.5):
        return "Tidak disimpan: fakta itu tidak ada di pesan pengguna. Simpan hanya yang benar-benar dikatakan pengguna."
    scope = ctx.bot["id"] if ctx.bot.get("memory_scope") == "own" else "shared"
    mid, new = memory.add_memory(scope, kind, fact)
    if not mid:
        return "Tidak disimpan (terlalu pendek)."
    return "Tersimpan di ingatan." if new else "Sudah ada di ingatan (diperbarui)."


@tool("recall", "Mencari di ingatan", "Search long-term memory for facts.", {"query": S("what to look for")}, ["query"])
async def recall(ctx: Ctx, query: str = "", **_):
    rows = memory.search_memories(ctx.bot, query, k=8)
    return "\n".join(f"- {r['text']}" for r in rows) or "Tidak ada ingatan yang cocok."


@tool("save_skill", "Menyimpan skill",
      "Save a reusable step-by-step procedure you just used successfully, so you can reuse it next time.",
      {"name": S("short name"), "when_to_use": S("one sentence"), "steps": S("numbered steps")},
      ["name", "steps"])
async def save_skill_tool(ctx: Ctx, name: str = "", when_to_use: str = "", steps="", **_):
    sid, new = memory.save_skill(ctx.bot["id"], name, when_to_use, steps, source="manual")
    return ("Skill baru tersimpan." if new else "Skill diperbarui.") if sid else "Skill tidak valid."


# ---------- jadwal ----------

def parse_when(when: str) -> float | None:
    when = (when or "").strip().lower()
    now = datetime.now().astimezone()
    m = re.match(r"^(?:dalam\s+|in\s+)?(\d+)\s*(menit|min|minutes?|m|jam|hours?|h|hari|days?|d)\b", when)
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = timedelta(minutes=n) if u[0] == "m" else timedelta(hours=n) if u[0] in "jh" else timedelta(days=n)
        return (now + delta).timestamp()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(when[:19], fmt).replace(tzinfo=now.tzinfo).timestamp()
        except ValueError:
            pass
    m = re.search(r"(besok|lusa|tomorrow)?\D*?(\d{1,2})[:.](\d{2})", when)
    if m:
        t = now.replace(hour=int(m.group(2)), minute=int(m.group(3)), second=0, microsecond=0)
        if m.group(1) in ("besok", "tomorrow"):
            t += timedelta(days=1)
        elif m.group(1) == "lusa":
            t += timedelta(days=2)
        elif t <= now:
            t += timedelta(days=1)
        return t.timestamp()
    return None


def next_repeat(ts: float, repeat: str) -> float | None:
    r = (repeat or "").lower().strip()
    if not r or r in ("none", "tidak", "sekali", "once"):
        return None
    m = re.match(r"(?:every|tiap|setiap)\s*(\d+)\s*(menit|min|m|jam|h|hours?)", r)
    if m:
        n = int(m.group(1))
        step = n * 60 if m.group(2)[0] == "m" else n * 3600
        return ts + max(step, 300)
    if r in ("hourly", "tiap jam", "setiap jam"):
        return ts + 3600
    if r in ("daily", "harian", "tiap hari", "setiap hari"):
        return ts + 86400
    if r in ("weekly", "mingguan", "tiap minggu", "setiap minggu"):
        return ts + 7 * 86400
    return None


@tool("schedule", "Membuat jadwal",
      "Schedule a reminder or a recurring task. kind=reminder just sends the message; kind=task makes you "
      "do the message as an instruction at that time (e.g. check gold price every morning) and send the result.",
      {"when": S("'YYYY-MM-DD HH:MM', 'HH:MM', 'besok 07:00', or 'in 30 minutes'"),
       "message": S("reminder text or task instruction"),
       "repeat": S("none | daily | weekly | hourly | 'every 2 hours'"),
       "kind": S("reminder | task")}, ["when", "message"])
async def schedule(ctx: Ctx, when: str = "", message: str = "", repeat: str = "none", kind: str = "reminder", **_):
    ts = parse_when(when)
    if not ts:
        return f"Waktu '{when}' tidak dimengerti. Pakai format 'YYYY-MM-DD HH:MM'."
    kind = "task" if kind == "task" else "reminder"
    jid = db.run("INSERT INTO jobs(bot_id,channel,ext_id,kind,text,next_run,repeat,created_at) VALUES(?,?,?,?,?,?,?,?)",
                 (ctx.bot["id"], ctx.channel, ctx.ext_id, kind, message, ts, repeat or "", time.time()))
    when_txt = datetime.fromtimestamp(ts).astimezone().strftime("%d-%m-%Y %H:%M")
    return f"Jadwal #{jid} dibuat: {when_txt}" + (f", diulang {repeat}" if next_repeat(ts, repeat) else "") + "."


@tool("list_schedules", "Melihat jadwal", "List active reminders and scheduled tasks.", {})
async def list_schedules(ctx: Ctx, **_):
    rows = db.q("SELECT * FROM jobs WHERE active=1 AND bot_id=? ORDER BY next_run", (ctx.bot["id"],))
    if not rows:
        return "Tidak ada jadwal aktif."
    return "\n".join(f"#{r['id']} {datetime.fromtimestamp(r['next_run']).astimezone():%d-%m %H:%M} "
                     f"[{r['kind']}{', ' + r['repeat'] if r['repeat'] else ''}] {r['text'][:80]}" for r in rows)


@tool("cancel_schedule", "Membatalkan jadwal", "Cancel a scheduled reminder/task by its number.",
      {"id": I("schedule number")}, ["id"])
async def cancel_schedule(ctx: Ctx, id=0, **_):
    db.run("UPDATE jobs SET active=0 WHERE id=?", (int(id),))
    return f"Jadwal #{id} dibatalkan."


# ---------- lain-lain ----------

@tool("server_status", "Cek server", "Check the server's RAM, CPU load, disk and loaded AI model.", {})
async def server_status(ctx: Ctx, **_):
    from .web import system_stats
    s = await system_stats()
    return json.dumps(s, ensure_ascii=False, indent=1)


@tool("create_bot", "Membuat bot",
      "Create a new specialised bot. tools: comma-separated from: web_search, read_webpage, browser, run_python, "
      "run_shell, list_files, read_file, write_file, remember, recall, save_skill, schedule, list_schedules, "
      "cancel_schedule, server_status, generate_image, send_file, ask_online.",
      {"name": S("bot name"), "persona": S("who the bot is, its job and style, 2-4 sentences, Indonesian"),
       "tools": S("comma-separated tool names"), "icon": S("one of: " + ", ".join(BOT_ICONS))}, ["name", "persona"])
async def create_bot(ctx: Ctx, name: str = "", persona: str = "", tools: str = "", icon: str = "bot", **_):
    names = [t.strip() for t in re.split(r"[,\s]+", tools if isinstance(tools, str) else ",".join(tools)) if t.strip() in REGISTRY
             and t.strip() != "create_bot"]
    if not names:
        names = ["web_search", "read_webpage", "remember", "recall", "save_skill"]
    bid = db.save_bot({"name": name, "persona": persona, "tools": names, "icon": icon if icon in BOT_ICONS else "bot"})
    return (f"Bot '{name}' dibuat (nama: {bid}) dengan alat: {', '.join(names)}. Pemilik bisa memilihnya di web "
            f"atau /bot di Telegram. Supaya punya akun Telegram sendiri: buat bot di @BotFather lalu kirim /tokenbot {bid} TOKEN.")


@tool("ask_online", "Bertanya ke AI online",
      "Ask a much smarter online AI for hard questions (complex reasoning, long writing, coding). Costs money; use only when needed.",
      {"question": S("the full question with all needed context")}, ["question"])
async def ask_online(ctx: Ctx, question: str = "", **_):
    res = await llm.chat([{"role": "user", "content": question}], model="online")
    return res["content"]




@tool("ask_bot", "Berkonsultasi dengan bot", "Ask another specialist bot for research or a second opinion. Read-only consultation; no external writes. Use a bot ID from the current bot roster. Returns the actual answer.", {"bot": S("target bot id"), "task": S("specific question with relevant context")}, ["bot", "task"])
async def ask_bot(ctx, bot: str, task: str, **_):
    from . import office
    limit = 4 if ctx.bot["id"] == "orchestrator" else 2
    if getattr(ctx, "delegations", 0) >= limit:
        return f"Error: maksimal {limit} konsultasi per giliran."
    ctx.delegations = getattr(ctx, "delegations", 0) + 1
    tid = office.enqueue(ctx.bot["id"], bot, task)
    db.run("UPDATE office_tasks SET status='working' WHERE id=?", (tid,))
    try:
        result = await office.consult(ctx.bot["id"], bot, task, tid)
        status = 'failed' if result.startswith(('Error:', 'Galat:')) else 'done'
    except Exception as exc:
        result, status = f"Error: {type(exc).__name__}", 'failed'
    db.run('UPDATE office_tasks SET status=?,result=?,updated_at=? WHERE id=?', (status, result[:6000], time.time(), tid))
    return ('Error: ' if status=='failed' else '') + f'<untrusted_content>\nBot {bot}: {result}\n</untrusted_content>'

ALL_TOOLS = list(REGISTRY)

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


@tool('find_tools', 'Mencari alat',
      'Find available tools for a task, including MCP/account/project tools. Search before guessing an unknown tool. Returns only tools assigned to this bot.',
      {'query': S('task or tool/domain keywords')}, ['query'])
async def find_tools(ctx, query='', **_):
    words = set(memory.words(query))
    ranked = []
    for name in ctx.bot.get('tools', []):
        if name == 'find_tools' or name not in REGISTRY:continue
        tool = REGISTRY[name]
        tokens = set(memory.words(name.replace('_',' ')+' '+tool.label+' '+tool.description))
        score = len(words & tokens)
        if score:ranked.append((score,name))
    names = [name for _,name in sorted(ranked,reverse=True)[:6]]
    ctx.exposed_tools = list(dict.fromkeys(getattr(ctx,'exposed_tools',[]) + names))
    return json.dumps([REGISTRY[name].schema()['function'] for name in names], ensure_ascii=False) if names else 'Tidak ada alat yang cocok dalam izin bot ini. Coba kata kunci lain atau tambahkan alat di Tim bot.'


@tool('inspect_app', 'Memeriksa aplikasi', 'Inspect Agen Mini editable source filenames and current harness, assigned tools and memory scope. Read-only; no secrets or live code edits.', {}, [])
async def inspect_app(ctx, **_):
    from . import repair, agent
    return json.dumps({'files': repair.files(), 'harness': agent.system_prompt(ctx.bot), 'tools': ctx.bot['tools'], 'memory_scope': ctx.bot['memory_scope'], 'guard': 'Code changes are proposals only. Owner review and GitHub Actions are required before release installation.'}, ensure_ascii=False)


@tool('propose_app_change', 'Mengusulkan perbaikan aplikasi', 'Propose a fix or feature for Agen Mini. Use inspect_app to find relevant files first. Creates a separate review draft, never edits or installs the live application.', {'prompt': S('Requested fix and acceptance criteria'), 'files': {'type':'array','items':{'type':'string'},'minItems':1,'maxItems':6}}, ['prompt','files'])
async def propose_app_change(ctx, prompt, files, **_):
    from . import repair
    return json.dumps(await repair.propose(prompt, files, ctx.bot['id']), ensure_ascii=False)


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


def _kerja_limits(project=False):
    if not project: resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    os.setsid()


async def _run_sandboxed(argv: list[str], timeout: int = 60, stdin: bytes | None = None, cwd=None, project=False) -> str:
    if os.name == "nt":
        from . import windows_execution
        return await windows_execution.run(argv,cwd or config.WORK_DIR,timeout,stdin,project)
    if os.name != "posix":
        return "Error: eksekusi belum didukung pada OS ini."
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    extra = {}
    if os.geteuid() == 0:
        extra = {"user": config.KERJA_UID, "group": config.KERJA_GID, "extra_groups": []}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(config.WORK_DIR), "LANG": "C.UTF-8",
           "TZ": config.TZ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg", "NODE_OPTIONS":"--max-old-space-size="+str(384 if project else 192), "GIT_TERMINAL_PROMPT":"0"}  # grafik matplotlib ke berkas
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.PIPE if stdin else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        cwd=str(cwd or config.WORK_DIR), env=env, preexec_fn=__import__("functools").partial(_kerja_limits,project=project), **extra)
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


def _ctx_workpath(ctx,path):
    folder=getattr(ctx,'project_folder',None)
    if not folder:return _workpath(path)
    root=_workpath(folder);name=str(path or '.').strip('/')
    if name==folder or name.startswith(folder+'/'):target=_workpath(name)
    else:target=_workpath(folder+'/'+name)
    if not target.is_relative_to(root):raise ValueError('Berkas harus tetap di dalam proyek aktif.')
    return target


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
    r"\bnc\s+-l|\bcrontab\b|\bssh\b|\bscp\b|Remove-Item|Stop-Process|Restart-Computer|\biex\b", re.I)
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
    p = _ctx_workpath(ctx,path)
    if not p.exists():
        return "Folder tidak ada."
    items = sorted(p.iterdir())[:200]
    return "\n".join(f"{i.name}/" if i.is_dir() else f"{i.name} ({i.stat().st_size} B)"
                     for i in items if not i.name.startswith(".")) or "(kosong)"


@tool("read_file", "Membaca berkas", "Read a text file from the workspace.", {"path": S("file path"), "start_line": I("first line, 1-based"), "max_lines": I("lines to read, max 400")}, ["path"])
async def read_file(ctx: Ctx, path: str = "", start_line: int = 1, max_lines: int = 0, **_):
    p = _ctx_workpath(ctx,path)
    if not p.is_file():
        return "Berkas tidak ada."
    t = p.read_text(encoding="utf-8", errors="replace")
    if max_lines or start_line!=1:
        lines=t.splitlines();start=max(0,int(start_line)-1);count=min(400,max(1,int(max_lines) or 100));return "\n".join(lines[start:start+count])[:16000]
    return t[:8000] + ("\n…(dipotong; gunakan start_line/max_lines untuk lanjut)" if len(t) > 8000 else "")


@tool("write_file", "Menulis berkas", "Write (overwrite) a text file in the workspace.",
      {"path": S("file path"), "content": S("text to write")}, ["path", "content"])
async def write_file(ctx: Ctx, path: str = "", content: str = "", **_):
    p = _ctx_workpath(ctx,path)
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
    if p.suffix=='.py':
        cache=p.parent/'__pycache__'
        if cache.is_dir():
            for bytecode in cache.iterdir():
                if bytecode.name.startswith(p.stem+'.') and bytecode.suffix=='.pyc':
                    try:bytecode.unlink()
                    except OSError:pass
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
    ctx.served_model = stats.get('served_model', '')
    office.phase('Memeriksa dan menyimpan halaman…', 'tool')
    from .projects import inspect_html
    checks=inspect_html(html)
    if not checks['ok']:return 'Error: '+ ' '.join(checks['errors'])
    from .projects import inspect_inline_js
    js_errors=await inspect_inline_js(html)
    if js_errors:return 'Error: JavaScript HTML belum valid: '+' '.join(js_errors)
    title=re.search(r'<title[^>]*>(.*?)</title>',html,re.I|re.S)
    basename=re.sub(r'[^a-z0-9]+','-',title.group(1).lower() if title else 'website').strip('-')[:70] or 'website'
    path = 'website-' + str(time.time_ns()) + '/'+basename+'.html'
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
    p = _ctx_workpath(ctx,path)
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
    name = str(name).strip()[:80]
    persona = str(persona).strip()[:4000]
    if not name or not persona:
        return "Error: nama dan peran spesialis wajib diisi."
    requested = [t.strip() for t in re.split(r"[,\s]+", tools if isinstance(tools, str) else ",".join(tools)) if t.strip()]
    forbidden = {"create_bot", "create_specialist", "delegate_task"}
    requested = [t for t in requested if t not in forbidden]
    permitted = set(ctx.bot.get("tools", [])) - forbidden
    unknown = [t for t in requested if t not in REGISTRY or t not in permitted]
    if unknown:
        return "Error: alat tidak tersedia atau di luar izin pembuat: " + ", ".join(unknown)
    names = list(dict.fromkeys(requested or [t for t in ("web_search", "read_webpage", "read_file", "recall") if t in permitted]))
    if not names:
        return "Error: tidak ada alat yang dapat diwariskan."
    # Reuse a matching specialist; do not silently replace an owner's bot.
    for bot in db.bots():
        if bot['name'].casefold() == name.casefold():
            return "Error: bot bernama sama sudah ada: " + bot['id'] + ". Gunakan bot itu atau pilih nama lain."
    if len(db.bots()) >= 40:
        return "Error: batas 40 bot tercapai; kelola spesialis yang sudah ada di Workspace."
    bid = db.save_bot({"name": name, "persona": persona + "\nKerjakan tugas berdasarkan bukti alat. Baca skill terkait; laporkan galat, kebutuhan kredensial, dan batas pengujian. Jangan mengklaim tindakan eksternal berhasil tanpa bukti.",
                       "tools": names, "icon": icon if icon in BOT_ICONS else "bot", "backend": ctx.bot.get('backend') or '', "model": ctx.bot.get('model') or ''})
    return json.dumps({"created": True, "bot": bid, "name": name, "tools": names, "next": "Gunakan delegate_task dengan ID bot ini untuk pekerjaan nyata."}, ensure_ascii=False)


@tool("create_specialist", "Membuat spesialis tugas", "Orchestrator creates a specialist for a missing domain. Give a specific role and comma-separated tools available to you. Cannot grant new permissions, nested delegation, or credentials. Returns actual bot ID for delegate_task.",
      {"name": S("specialist name"), "persona": S("domain expertise, task, constraints and acceptance checks"), "tools": S("comma-separated tools available to the orchestrator"), "icon": S("bot icon")}, ["name", "persona", "tools"])
async def create_specialist(ctx, **kwargs):
    if ctx.bot.get('id') != 'orchestrator':
        return "Error: hanya orchestrator yang dapat membuat spesialis tugas."
    return await create_bot(ctx, **kwargs)


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

@tool('inspect_website','Memeriksa website','Read and inspect the actual saved HTML: document structure, viewport and local anchor targets. Returns factual checks, not a claim of browser execution.',{'path':S('HTML file in workspace')},['path'])
async def inspect_website(ctx,path='',**_):
    from .projects import inspect_html
    p=_workpath(path)
    if not p.is_file():return 'Error: berkas belum ada.'
    return json.dumps(inspect_html(p.read_text(encoding='utf-8')),ensure_ascii=False)

@tool('build_project','Membuat proyek multi-berkas','Create a functional game, web app or application project with multiple files, verify file references and deliver a ZIP. State backend/dependency limits accurately.',{'brief':S('complete project requirements')},['brief'])
async def build_project(ctx,brief='',on_event=None,**_):
    from . import projects
    return await projects.generate(brief,ctx,on_event)

@tool('delegate_task','Menugaskan bot','Orchestrator assigns actual work to a specialist using its permitted tools; transfers real files/results to the owner and preserves approval requirements.',{'bot':S('specialist bot ID'),'task':S('specific task with owner requirements')},['bot','task'])
async def delegate_task(ctx,bot='',task='',**_):
    from . import office
    result=await office.execute(ctx,bot,task)
    if result.get('approval'):ctx.pending_approval=result['approval']
    return result.get('text','Error: delegasi tidak menghasilkan jawaban.')

@tool('clone_repository','Mengambil repositori GitHub','Clone a public or authorized private GitHub repository into a NEW workspace folder. Uses verified host login when available without exposing tokens. No push, submodules or overwriting existing work.',{'url':S('https://github.com/owner/repo'),'folder':S('new relative workspace folder')},['url','folder'])
async def clone_repository(ctx,url='',folder='',**_):
    if not folder or folder=='.':return 'Error: pilih folder kerja baru.'
    from . import repository
    return await repository.clone(url,_workpath(folder))

_project_command_lock=asyncio.Lock()

@tool('run_project_command','Build atau uji proyek','Run one build/test command inside a workspace project as kerja, bounded timeout and Node heap. Actual exit code is returned; never equate syntax checks with complete app validation.',{'folder':S('workspace project folder'),'command':S('build/test shell command'),'timeout':I('seconds, maximum 300')},['folder','command'],danger=lambda a:'Perintah proyek membutuhkan izin karena dapat menghapus atau mengubah data.' if DANGER_SHELL.search(a.get('command','')) else None)
async def run_project_command(ctx,folder='',command='',timeout=180,**_):
    scope=getattr(ctx,'project_folder',None)
    target=_ctx_workpath(ctx,'.' if scope and folder in ('','.',Path(scope).name) else folder) if scope else _workpath(folder)
    if not target.is_dir():return 'Error: folder proyek belum ada.'
    async with _project_command_lock:
        result=await _run_sandboxed(['bash','-o','pipefail','-c',command],timeout=min(max(int(timeout),1),300),cwd=target,project=True)
        if not result.startswith('[kode keluar 0]') and 'No such file or directory' in result:
            result+='\nFolder kerja perintah: '+str(target)+'. Gunakan path relatif ke folder ini; jangan ulangi awalan projects/project-N.'
        return result

@tool('inspect_project','Memeriksa proyek','Read project tree/manifests and verify JSON/Python/JavaScript syntax without running installation scripts. Reports actual checks and remaining build/test requirements.',{'folder':S('workspace project folder')},['folder'])
async def inspect_project(ctx,folder='',**_):
    from .project_jobs import inspect
    return json.dumps(await inspect(getattr(ctx,'project_folder',None) or folder),ensure_ascii=False)

@tool('start_project','Memulai proyek berkelanjutan','Create a persistent multi-milestone project coordinated by orchestrator, optionally from a public repository. Work progresses serially; status/checkpoints survive restart and can be paused/resumed.',{'brief':S('detailed project objective and acceptance criteria'),'repository':S('optional public GitHub URL')},['brief'])
async def start_project(ctx,brief='',repository='',**_):
    from . import project_jobs
    pid=project_jobs.create(ctx,brief,repository)
    return f'Proyek #{pid} masuk antrean. Lihat rencana, hasil tiap tahap dan pemeriksaan di Workspace. Belum dianggap selesai.'


@tool('edit_project_file','Mengembangkan berkas proyek','Implement or update one real file in an existing project using bounded raw-code generation, preserving existing conventions. Reads current file/README/AGENTS; saves and syntax-checks. Use run_project_command for actual build/integration tests afterward.',{'folder':S('existing workspace project'),'path':S('relative project file'),'instructions':S('specific change, acceptance criteria and imports/interfaces to preserve')},['folder','path','instructions'])
async def edit_project_file(ctx,folder='',path='',instructions='',**_):
    from . import projects
    folder=getattr(ctx,'project_folder',None) or folder
    root=_workpath(folder)
    if not root.is_dir():return 'Error: folder proyek belum ada.'
    if path.startswith(folder+'/'):path=path[len(folder)+1:]
    target=_workpath(folder+'/'+projects.safe_name(path))
    if not target.is_relative_to(root):return 'Error: berkas harus berada dalam proyek.'
    original=target.read_text() if target.is_file() else ''
    if len(original)>(6000 if llm.active_backend()=='local' else 24000):return 'Error: berkas terlalu panjang untuk satu perubahan model; baca bagian relevan dan edit melalui perintah proyek.'
    context={name:(root/name).read_text(errors='replace')[:3000] for name in ('AGENTS.md','README.md','package.json') if (root/name).is_file()}
    # Include actual adjacent contracts: SQL columns and imported APIs must not be guessed.
    related={};remaining=1800 if llm.active_backend()=='local' else 12000
    candidates=[target.parent/name for name in ('db.py','models.py','schema.sql','config.py','auth.py','requirements.txt','package.json','pyproject.toml')]
    candidates += [target.parent.parent/name for name in ('requirements.txt','package.json','pyproject.toml')]
    for source in candidates:
        source=source.resolve()
        if source==target or not source.is_relative_to(root) or not source.is_file() or not remaining:continue
        name=str(source.relative_to(root))
        if name in related:continue
        text=source.read_text(errors='replace')[:min(remaining,6000)];related[name]=text;remaining-=len(text)
    context['related_source']=related
    result=await llm.chat([{'role':'system','content':'Implement ONE COMPLETE source file. Return raw file text only, no markdown fences. Preserve existing behavior, conventions, interfaces and project AGENTS instructions; change only requested functionality. Use the actual imported interfaces and SQL columns in related_source; never invent them. Authentication must validate an opaque session on the server, never trust a seller_id cookie/header as identity. No TODO placeholders, fake APIs, secrets, or unsupported success claims. Finish the whole file.'},
                          {'role':'user','content':json.dumps({'file':path,'task':instructions,'project':context,'current_source':original},ensure_ascii=False)}],max_tokens=2400 if llm.active_backend()=='local' else 6000,temperature=.2)
    if result.get('stats',{}).get('finish_reason') in ('length','max_tokens'):
        return 'Error: keluaran model terpotong oleh batas token. Berkas asli dipertahankan; lakukan perubahan lebih kecil melalui perintah proyek.'
    content=re.sub(r'^```[^\n]*\n','',result['content'].strip());content=re.sub(r'\n```\s*$','',content)
    if not content:return 'Error: model menghasilkan berkas kosong.'
    if target.suffix=='.py':compile(content,str(target),'exec')
    if target.suffix=='.json':json.loads(content)
    if target.suffix=='.html' and not projects.inspect_html(content)['ok']:return 'Error: struktur HTML belum valid.'
    # Validate JavaScript privately before replacing existing code.
    if target.suffix=='.js':
        async with _project_command_lock:
            check=await _run_sandboxed(['node','--check','--input-type=module'],timeout=15,stdin=content.encode(),cwd=root,project=True)
        if not check.startswith('[kode keluar 0]'):return 'Error: sintaks JavaScript belum valid: '+check
    await write_file(ctx,str(target.relative_to(config.WORK_DIR.resolve())),content)
    if target.read_text()!=content:return 'Error: verifikasi isi berkas gagal.'
    return 'Berkas diperbarui dan dibaca ulang: '+folder+'/'+path+' ('+str(len(content.encode()))+' byte). Jalankan build/test proyek; pemeriksaan sintaks belum membuktikan runtime.'

@tool('preview_project','Uji frontend tersimpan','Open a real workspace HTML in an installed browser and check JavaScript exceptions. Optional checks is a JavaScript expression for actual clicks/assertions. Visual layout/WebGL requires Chromium; Lightpanda checks DOM/JS only. Browser closes after testing.',{'path':S('workspace HTML path'),'checks':S('optional JS expression returning verification results'),'require_webgl':{'type':'boolean','description':'require real Chromium WebGL rendering capability'}},['path'])
async def preview_project(ctx,path='',checks='',require_webgl=False,**_):
    from . import browser
    page=_ctx_workpath(ctx,path)
    if not page.is_file() or page.suffix.lower()!='.html':return 'Error: berkas HTML belum tersedia.'
    if require_webgl and not browser.chromium_bin():return 'Error: uji WebGL memerlukan Chromium opsional; browser ringan hanya memeriksa DOM/JavaScript, bukan rendering 3D.'
    key='preview:'+ctx.bot['id'];session=None;runner=None
    from aiohttp import web
    root=page.parent
    async def serve(request):
        relative=request.match_info['tail'] or page.name;target=(root/relative).resolve()
        allowed={'.html','.htm','.js','.css','.json','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff','.woff2','.txt'}
        if not target.is_relative_to(root) or any(part.startswith('.') for part in Path(relative).parts) or target.suffix.lower() not in allowed or not target.is_file():raise web.HTTPNotFound()
        return web.FileResponse(target)
    async with _project_command_lock:
        try:
            app=web.Application();app.router.add_get('/{tail:.*}',serve);runner=web.AppRunner(app);await runner.setup()
            site=web.TCPSite(runner,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
            from urllib.parse import quote
            url='http://127.0.0.1:'+str(port)+'/'+quote(page.name)
            session=await browser.pool.get(key,fresh_engine='chromium' if require_webgl else None,local_preview=True)
            await session.send('Page.navigate',{'url':url},session=True)
            await session.wait_ready()
            loaded=await session.eval('({url:location.href,title:document.title,body:!!document.body,buttons:document.querySelectorAll("button").length})')
            if not loaded or loaded.get('url')!=url or not loaded.get('body'):return 'Error: browser belum berhasil memuat berkas.'
            assertions=await session.eval(checks) if checks else None
            await asyncio.sleep(.3)
            errors=[e.get('params',{}).get('exceptionDetails',{}).get('exception',{}).get('description') or e.get('params',{}).get('exceptionDetails',{}).get('text') for e in session.events if e.get('method')=='Runtime.exceptionThrown']
            report={'engine':session.engine,'document':loaded,'assertions':assertions,'js_errors':errors,'note':'DOM/JS smoke test. Lightpanda tidak membuktikan layout/WebGL. Semua alur aplikasi/backend tetap memerlukan pengujian khusus.'}
            if session.engine=='chromium':
                report['viewports']=[]
                for width in (320,390,430,1280):
                    await session.send('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width<600},session=True)
                    report['viewports'].append(await session.eval('({width:innerWidth,documentWidth:document.documentElement.scrollWidth})'))
            return ('Error: frontend belum lulus. ' if errors or assertions is False or isinstance(assertions,dict) and assertions.get('ok') is False else '')+json.dumps(report,ensure_ascii=False)
        except Exception as exc:return 'Error: preview belum berhasil: '+str(exc)[:500]
        finally:
            if session:await session.close();browser.pool.sessions.pop(key,None)
            if runner:await runner.cleanup()

@tool('inspect_integrations','Memeriksa akun host','Read actual host CLI installation and verified GitHub/Cloudflare connection state. Never exposes tokens.',{},[])
async def inspect_integrations(ctx,**_):
    from . import integrations
    return json.dumps(integrations.status(),ensure_ascii=False)

@tool('github_read','Membaca GitHub tersambung','Use the verified host GitHub login to GET /user, /user/repos?per_page=30, /repos/owner/repo, or README/languages/issues?per_page=10. No writes, emails or token exposure.',{'path':S('allowlisted GitHub API path')},['path'])
async def github_read(ctx,path='',**_):
    from . import integrations
    return await integrations.read('github',path)

@tool('cloudflare_read','Membaca Cloudflare tersambung','Use verified host Cloudflare credential to GET /accounts?per_page=20 or /zones?per_page=20. No deployment, DNS changes or tunnel creation.',{'path':S('allowlisted Cloudflare path')},['path'])
async def cloudflare_read(ctx,path='',**_):
    from . import integrations
    return await integrations.read('cloudflare',path)


@tool('social_status','Memeriksa koneksi akun','Read verified status of Threads, Instagram, Meta Ads and YouTube without exposing credentials.',{},[])
async def social_status(ctx,**_):
    from . import social_connections
    return json.dumps(social_connections.status(),ensure_ascii=False)

@tool('social_read','Membaca akun/konten','Read connected social profile/posts/campaigns/videos using official APIs. Missing credentials/permissions/quota are reported. No posting, ad changes or transactions.',{'provider':S('threads | instagram | meta_ads | youtube'),'operation':S('profile | posts | campaigns | videos'),'identifier':S('optional ad account act_ID or YouTube playlist ID')},['provider'])
async def social_read(ctx,provider='',operation='profile',identifier='',**_):
    from . import social_connections
    try:return json.dumps(await social_connections.read(provider,operation,identifier),ensure_ascii=False)[:16000]
    except Exception as exc:return 'Error: '+str(exc)

@tool('social_publish','Mempublikasikan konten','Publish explicit owner-approved text to Threads or image+caption to Instagram. Requires connected write permission; successful provider ID is required. Never use as a connection test.',{'provider':S('threads | instagram'),'text':S('exact final post/caption'),'image_url':S('public HTTPS image URL for Instagram')},['provider','text'],danger=lambda a:'Konten akan dipublikasikan ke '+a.get('provider','akun')+'. Tinjau teks/URL persis sebelum mengizinkan.')
async def social_publish(ctx,provider='',text='',image_url='',**_):
    from . import social_connections
    try:return json.dumps(await social_connections.publish(provider,text,image_url),ensure_ascii=False)
    except Exception as exc:return 'Error: '+str(exc)

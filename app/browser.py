"""Web: cari, baca, dan browser interaktif.

Tangga hemat RAM:
  1. unduh HTML biasa + ambil isi utama (trafilatura)          ~0 MB tambahan
  2. Lightpanda (browser khusus agen, menjalankan JavaScript)     ~50-150 MB
  3. Chromium headless (paling kompatibel, paling berat)          ~300-500 MB, model dilepas dulu bila RAM sempit
Browser dijalankan sebagai user 'kerja' dan dimatikan sendiri setelah 5 menit menganggur.
"""
import asyncio
import html as html_lib
import json
import os
import re
import shutil
import time
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import aiohttp
from yarl import URL

from . import config, db, llm

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"}


def _run_as_kerja() -> dict:
    if os.geteuid() == 0:
        return {"user": config.KERJA_UID, "group": config.KERJA_GID, "extra_groups": []}
    return {}


def mem_available_mb() -> int:
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 9999


# ---------- pencarian ----------

async def search(query: str, n: int = 5) -> list[dict]:
    """DuckDuckGo → Bing → Brave → Wikipedia. SearXNG didahulukan bila diisi.
    DNS aman (net.py) membuat DDG tetap terjangkau walau DNS jaringan membelokkannya."""
    errors = []
    searx = db.setting("searx_url")
    engines = ([("searx", _search_searx)] if searx else []) + [
        ("ddg", _search_ddg), ("bing", _search_bing), ("brave", _search_brave), ("wikipedia", _search_wiki)]
    for name, fn in engines:
        try:
            res = [r for r in await fn(query, n) if r["url"].startswith("http")]
            if res:
                return res
            errors.append(f"{name}: kosong")
        except Exception as e:
            errors.append(f"{name}: {str(e)[:80]}")
    raise RuntimeError("Pencarian gagal (" + "; ".join(errors) + ")")


# Mesin pencari memberi halaman HTML sederhana kalau identitas peramban-nya sederhana.
SIMPLE_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"}


async def _get_html(url, **kw):
    from lxml import html as lh
    async with llm.session().get(url, headers=SIMPLE_UA, timeout=aiohttp.ClientTimeout(total=20), **kw) as r:
        return lh.fromstring(await r.text())


def _clean(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip() if el is not None else ""


async def _search_searx(query, n):
    url = db.setting("searx_url").rstrip("/") + "/search"
    async with llm.session().get(url, params={"q": query, "format": "json"}, headers=HEADERS,
                                 timeout=aiohttp.ClientTimeout(total=20)) as r:
        data = await r.json(content_type=None)
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
            for x in data.get("results", [])[:n]]


def _bing_real_url(href: str) -> str:
    """Tautan Bing /ck/a?...&u=a1<base64> → alamat aslinya."""
    if "bing.com/ck/a" not in href:
        return href
    u = parse_qs(urlparse(href).query).get("u", [""])[0]
    if u.startswith("a1"):
        import base64
        b = u[2:] + "=" * (-len(u[2:]) % 4)
        try:
            return base64.urlsafe_b64decode(b).decode()
        except Exception:
            pass
    return href


async def _search_bing(query, n):
    doc = await _get_html(f"https://www.bing.com/search?q={quote_plus(query)}&setlang=id&cc=ID")
    out = []
    for li in doc.cssselect("li.b_algo"):
        a = li.cssselect("h2 a")
        if not a:
            continue
        p = li.cssselect(".b_caption p") or li.cssselect("p")
        out.append({"title": _clean(a[0]), "url": _bing_real_url(a[0].get("href", "")),
                    "snippet": _clean(p[0]) if p else ""})
        if len(out) >= n:
            break
    return out


async def _search_brave(query, n):
    doc = await _get_html(f"https://search.brave.com/search?q={quote_plus(query)}")
    out = []
    for sn in doc.cssselect('div.snippet[data-type="web"]'):
        a = sn.cssselect("a[href^='http']")
        if not a:
            continue
        t = sn.cssselect(".title")
        d = sn.cssselect(".snippet-description") or sn.cssselect(".generic-snippet .content") or             sn.cssselect("[class*=description]") or sn.cssselect(".content")
        out.append({"title": (t[0].get("title") or _clean(t[0])) if t else _clean(a[0]), "url": a[0].get("href"),
                    "snippet": _clean(d[0]) if d else ""})
        if len(out) >= n:
            break
    return out


async def _search_wiki(query, n):
    """Cadangan terakhir: pencarian Wikipedia Indonesia (API resmi, tidak memblokir robot)."""
    async with llm.session().get("https://id.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": n},
            headers={"User-Agent": "AgenMini/0.1 (asisten pribadi)"}, timeout=aiohttp.ClientTimeout(total=15)) as r:
        data = await r.json(content_type=None)
    return [{"title": x["title"], "url": "https://id.wikipedia.org/wiki/" + quote_plus(x["title"].replace(" ", "_")),
             "snippet": html_lib.unescape(re.sub(r"<[^>]+>", "", x.get("snippet", "")))} for x in data.get("query", {}).get("search", [])]


async def _search_ddg(query, n):
    from lxml import html as lh
    async with llm.session().post("https://html.duckduckgo.com/html/", data={"q": query, "kl": "id-id"},
                                  headers=SIMPLE_UA, timeout=aiohttp.ClientTimeout(total=20)) as r:
        doc = lh.fromstring(await r.text())
    out = []
    for res in doc.cssselect("div.result"):
        a = res.cssselect("a.result__a")
        if not a:
            continue
        href = a[0].get("href", "")
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com/y.js" in href:  # iklan
            continue
        snip = res.cssselect(".result__snippet")
        out.append({"title": _clean(a[0]), "url": href, "snippet": _clean(snip[0]) if snip else ""})
        if len(out) >= n:
            break
    return out


# ---------- membaca halaman ----------

def extract_main(html: str, url: str = "") -> str:
    import trafilatura
    text = trafilatura.extract(html, url=url or None, include_comments=False, include_tables=True,
                               favor_recall=True, output_format="markdown") or ""
    if len(text) < 200:
        from lxml import html as lh
        try:
            doc = lh.fromstring(html)
            for bad in doc.xpath("//script|//style|//noscript|//svg"):
                bad.drop_tree()
            alt = re.sub(r"\n\s*\n+", "\n\n", doc.text_content())
            if len(alt.strip()) > len(text):
                text = alt.strip()
        except Exception:
            pass
    return text


def pick_relevant(text: str, question: str, limit: int) -> str:
    """Halaman panjang dipotong; kalau ada pertanyaan, ambil bagian yang paling nyambung."""
    if len(text) <= limit:
        return text
    if not question:
        return text[:limit] + "\n…(dipotong)"
    from .memory import words
    qw = set(words(question))
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    scored = sorted(range(len(paras)), key=lambda i: -len(qw & set(words(paras[i]))))
    keep, total = set(), 0
    for i in [0] + scored:
        if total + len(paras[i]) > limit:
            continue
        keep.add(i)
        total += len(paras[i])
    return "\n\n".join(paras[i] for i in sorted(keep)) + "\n…(hanya bagian yang relevan)"


async def check_public(url: str):
    """Tolak alamat internal (127.0.0.1, jaringan Docker, panel 1Panel, metadata cloud 169.254.x.x).
    Dicek juga untuk tiap pengalihan, supaya halaman web tidak bisa menyuruh agen mengintip server sendiri."""
    import ipaddress
    import socket
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise RuntimeError("Hanya alamat http/https.")
    from .net import resolve_ips
    try:
        ips = await resolve_ips(u.hostname)
    except (socket.gaierror, OSError):
        raise RuntimeError(f"Nama situs '{u.hostname}' tidak ditemukan.")
    for raw in ips:
        ip = ipaddress.ip_address(raw)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise RuntimeError("Alamat internal/privat tidak boleh dibuka.")


async def fetch_plain(url: str) -> tuple[str, str]:
    for _ in range(6):
        await check_public(url)
        async with llm.session().get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=25),
                                     allow_redirects=False) as r:
            if r.status in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                url = str(r.url.join(URL(r.headers["Location"])))
                continue
            return await _read_body(r)
    raise RuntimeError("Terlalu banyak pengalihan.")


async def _read_body(r) -> tuple[str, str]:
    ctype = r.headers.get("Content-Type", "")
    if "pdf" in ctype:
        return "", "pdf"
    chunks, total = [], 0
    async for chunk in r.content.iter_chunked(65536):  # read(n) hanya memberi yang sudah tiba, bukan seluruhnya
        chunks.append(chunk)
        total += len(chunk)
        if total >= 5_000_000:
            break
    raw = b"".join(chunks)
    html = raw.decode(r.charset or "utf-8", errors="replace")
    if "html" not in ctype and "xml" not in ctype:
        return html, "text"
    return html, "html"


async def _cli_dump(cmd: list[str], timeout: int = 40) -> str:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                                                cwd=str(config.WORK_DIR), **_run_as_kerja())
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("waktu habis")
    return out.decode("utf-8", errors="replace")


def chromium_bin() -> str | None:
    return shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")


async def read_page(url: str, question: str = "", limit: int = 6000, plain_only: bool = False) -> dict:
    if not re.match(r"^https?://", url):
        url = "https://" + url
    await check_public(url)
    engine = db.setting("browser_engine") or "auto"
    notes, text = [], ""
    if plain_only:  # dipakai web_search untuk mengintip sumber teratas: cepat, tanpa browser
        html, kind = await fetch_plain(url)
        text = html if kind == "text" else extract_main(html, url)
        return {"url": url, "text": pick_relevant(text, question, limit) if kind != "pdf" else "", "via": "unduh biasa"}
    if engine == "auto":
        try:
            html, kind = await fetch_plain(url)
            if kind == "pdf":
                return {"url": url, "text": "(Berkas PDF belum bisa dibaca.)", "via": "tidak ada"}
            text = html if kind == "text" else extract_main(html, url)
            if len(text) >= 400 and "enable javascript" not in text.lower():
                return {"url": url, "text": pick_relevant(text, question, limit), "via": "unduh biasa"}
            notes.append("unduh biasa: isi terlalu sedikit")
        except Exception as e:
            notes.append(f"unduh biasa: {e}")
    if engine in ("auto", "lightpanda") and shutil.which("lightpanda"):
        try:
            html = await _cli_dump(["lightpanda", "fetch", "--block-private-networks", "--dump", "html", url])
            t2 = extract_main(html, url)
            if len(t2) >= 200:
                return {"url": url, "text": pick_relevant(t2, question, limit), "via": "lightpanda"}
            text = text if len(text) > len(t2) else t2
            notes.append("lightpanda: isi terlalu sedikit")
        except Exception as e:
            notes.append(f"lightpanda: {e}")
    if engine in ("auto", "chromium") and chromium_bin():
        try:
            if mem_available_mb() < 700:
                await llm.unload()
            html = await _cli_dump([chromium_bin(), "--headless=new", "--no-sandbox", "--disable-gpu",
                                    "--disable-dev-shm-usage", "--no-first-run", f"--user-agent={UA}",
                                    "--virtual-time-budget=8000", "--dump-dom", url], timeout=60)
            t3 = extract_main(html, url)
            if len(t3) > len(text):
                return {"url": url, "text": pick_relevant(t3, question, limit), "via": "chromium"}
        except Exception as e:
            notes.append(f"chromium: {e}")
    if text:
        return {"url": url, "text": pick_relevant(text, question, limit), "via": "sebagian", "notes": notes}
    raise RuntimeError("Halaman tidak bisa dibaca (" + "; ".join(notes) + ")")


# ---------- browser interaktif lewat CDP ----------

INDEX_JS = r"""
(() => {
  const sel = 'a[href],button,input:not([type=hidden]),textarea,select,[role=button],[onclick]';
  const els = Array.from(document.querySelectorAll(sel)).slice(0, 300);
  window.__agen = els;
  const label = e => (e.innerText || e.value || e.placeholder || e.getAttribute('aria-label') || e.title ||
                      e.name || e.id || '').replace(/\s+/g, ' ').trim().slice(0, 70);
  const items = [];
  els.forEach((e, i) => {
    const t = e.tagName.toLowerCase();
    const kind = t === 'a' ? 'tautan' : (t === 'input' || t === 'textarea' || t === 'select') ? ('isian:' + (e.type || t)) : 'tombol';
    const l = label(e);
    if (!l && kind === 'tautan') return;
    items.push(i + ') [' + kind + '] ' + l);
  });
  const body = (document.body ? document.body.innerText : '').replace(/\n\s*\n+/g, '\n\n').trim();
  return JSON.stringify({title: document.title, url: location.href, text: body.slice(0, 5000), items: items.slice(0, 60)});
})()
"""


class CDP:
    def __init__(self, engine: str, proc, port: int):
        self.engine, self.proc, self.port = engine, proc, port
        self.ws = None
        self.session_id = None
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader = None
        self.last_used = time.time()
        self.events: list[dict] = []

    async def connect(self):
        ws_url = f"ws://127.0.0.1:{self.port}"
        for _ in range(40):
            try:
                async with llm.session().get(f"http://127.0.0.1:{self.port}/json/version",
                                             timeout=aiohttp.ClientTimeout(total=2)) as r:
                    ws_url = (await r.json(content_type=None)).get("webSocketDebuggerUrl") or ws_url
                break
            except Exception:
                await asyncio.sleep(0.25)
        self.ws = await llm.session().ws_connect(ws_url, max_msg_size=50_000_000, heartbeat=30)
        self._reader = asyncio.create_task(self._read())
        ctx = await self.send("Target.createBrowserContext", {})
        target = await self.send("Target.createTarget", {"url": "about:blank", "browserContextId": ctx.get("browserContextId")})
        att = await self.send("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})
        self.session_id = att["sessionId"]
        await self.send("Page.enable", {}, session=True)
        await self.send("Runtime.enable", {}, session=True)

    async def _read(self):
        async for msg in self.ws:
            try:
                data = json.loads(msg.data)
            except Exception:
                continue
            if "id" in data and data["id"] in self._pending:
                fut = self._pending.pop(data["id"])
                if not fut.done():
                    fut.set_result(data)
            elif "method" in data:
                self.events.append(data)
                self.events = self.events[-50:]

    async def send(self, method, params, session=False, timeout=30):
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params}
        if session:
            msg["sessionId"] = self.session_id
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self.ws.send_str(json.dumps(msg))
        data = await asyncio.wait_for(fut, timeout)
        if "error" in data:
            raise RuntimeError(f"{method}: {data['error'].get('message')}")
        self.last_used = time.time()
        return data.get("result", {})

    async def eval(self, expr: str, timeout=20):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True},
                            session=True, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("text", "galat JavaScript"))
        return r.get("result", {}).get("value")

    async def wait_ready(self, max_s=15):
        t0 = time.time()
        await asyncio.sleep(0.8)
        while time.time() - t0 < max_s:
            try:
                if await self.eval("document.readyState", timeout=5) == "complete":
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.0)

    async def snapshot(self) -> dict:
        raw = await self.eval(INDEX_JS)
        return json.loads(raw or "{}")

    async def close(self):
        try:
            if self.ws:
                await self.ws.close()
        except Exception:
            pass
        if self._reader:
            self._reader.cancel()
        try:
            self.proc.kill()
        except Exception:
            pass


class BrowserPool:
    """Satu sesi browser per percakapan; hanya satu proses browser berjalan."""

    def __init__(self):
        self.sessions: dict[str, CDP] = {}
        self.lock = asyncio.Lock()

    async def _launch(self, engine: str) -> CDP:
        port = 9222 if engine == "lightpanda" else 9223
        if engine == "lightpanda":
            cmd = ["lightpanda", "serve", "--host", "127.0.0.1", "--port", str(port), "--block-private-networks"]
        else:
            if mem_available_mb() < 700:
                await llm.unload()
            cmd = [chromium_bin(), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                   "--no-first-run", f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
                   f"--user-agent={UA}", f"--user-data-dir={config.WORK_DIR}/.chromium", "about:blank"]
        env = dict(os.environ, LIGHTPANDA_DISABLE_TELEMETRY="true", HOME=str(config.WORK_DIR))
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.DEVNULL, env=env,
                                                    cwd=str(config.WORK_DIR), **_run_as_kerja())
        cdp = CDP(engine, proc, port)
        try:
            await asyncio.wait_for(cdp.connect(), 25)
        except Exception:
            await cdp.close()
            raise
        return cdp

    async def get(self, key: str, fresh_engine: str | None = None) -> CDP:
        async with self.lock:
            cur = self.sessions.get(key)
            if cur and (fresh_engine is None or cur.engine == fresh_engine):
                return cur
            for k, s in list(self.sessions.items()):  # hanya satu browser hidup
                await s.close()
                self.sessions.pop(k, None)
            pref = db.setting("browser_engine") or "auto"
            engines = [fresh_engine] if fresh_engine else (
                ["lightpanda", "chromium"] if pref == "auto" else [pref])
            last = None
            for eng in engines:
                if eng == "lightpanda" and not shutil.which("lightpanda"):
                    continue
                if eng == "chromium" and not chromium_bin():
                    continue
                try:
                    s = await self._launch(eng)
                    self.sessions[key] = s
                    return s
                except Exception as e:
                    last = e
            raise RuntimeError(f"Browser tidak bisa dijalankan: {last}")

    async def reap(self):
        """Dipanggil berkala: tutup browser yang menganggur > 5 menit."""
        for k, s in list(self.sessions.items()):
            if time.time() - s.last_used > 300:
                await s.close()
                self.sessions.pop(k, None)


pool = BrowserPool()


def _fmt(snap: dict, engine: str) -> str:
    items = "\n".join(snap.get("items", [])) or "(tidak ada)"
    return (f"Judul: {snap.get('title', '')}\nURL: {snap.get('url', '')}\n(mesin: {engine})\n\n"
            f"Isi halaman:\n{snap.get('text', '')[:4000]}\n\nElemen yang bisa dipakai (nomor):\n{items}")


async def browse(key: str, action: str, url: str = "", target: int | None = None, text: str = "") -> str:
    action = (action or "open").lower()
    if action in ("open", "buka", "goto", "navigate"):
        if not url:
            return "Butuh url untuk action=open."
        if not re.match(r"^https?://", url):
            url = "https://" + url
        await check_public(url)
        s = await pool.get(key)
        nav = await s.send("Page.navigate", {"url": url}, session=True)
        if nav.get("errorText"):
            return f"Halaman gagal dibuka ({nav['errorText']}). Situs mungkin diblokir atau sedang mati."
        await s.wait_ready()
        snap = await s.snapshot()
        if len(snap.get("text", "")) < 100 and s.engine == "lightpanda" and chromium_bin():
            s = await pool.get(key, fresh_engine="chromium")
            await s.send("Page.navigate", {"url": url}, session=True)
            await s.wait_ready()
            snap = await s.snapshot()
        return _fmt(snap, s.engine)
    s = pool.sessions.get(key)
    if not s:
        return "Belum ada halaman terbuka. Pakai action=open dengan url dulu."
    if action in ("click", "klik"):
        if target is None:
            return "Butuh nomor elemen (target)."
        href = await s.eval(f"(()=>{{const e=window.__agen&&window.__agen[{int(target)}]; if(!e) return 'X';"
                            f" if(e.tagName==='A' && e.href && !e.href.startsWith('javascript')) return e.href;"
                            f" e.click(); return ''}})()")
        if href == "X":
            return f"Elemen nomor {target} tidak ada. Buka ulang halaman untuk melihat daftar terbaru."
        if href:
            await check_public(href)
            await s.send("Page.navigate", {"url": href}, session=True)
        await s.wait_ready()
        return _fmt(await s.snapshot(), s.engine)
    if action in ("type", "isi", "fill"):
        if target is None:
            return "Butuh nomor isian (target) dan text."
        js_text = json.dumps(text)
        ok = await s.eval(
            f"(()=>{{const e=window.__agen&&window.__agen[{int(target)}]; if(!e) return false; e.focus();"
            f" e.value={js_text}; e.dispatchEvent(new Event('input',{{bubbles:true}}));"
            f" e.dispatchEvent(new Event('change',{{bubbles:true}})); return true}})()")
        if not ok:
            return f"Isian nomor {target} tidak ada."
        return f"Sudah diisi. Untuk mengirim, pakai action=submit target={target} atau klik tombolnya."
    if action in ("submit", "kirim", "enter"):
        await s.eval(
            f"(()=>{{const e=window.__agen&&window.__agen[{int(target or 0)}]; const f=e&&e.form;"
            f" if(f){{ if(f.requestSubmit) f.requestSubmit(); else f.submit(); return true}}"
            f" if(e) e.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',bubbles:true}})); return false}})()")
        await s.wait_ready()
        return _fmt(await s.snapshot(), s.engine)
    if action in ("read", "baca", "snapshot"):
        return _fmt(await s.snapshot(), s.engine)
    if action in ("back", "kembali"):
        await s.eval("history.back()")
        await s.wait_ready()
        return _fmt(await s.snapshot(), s.engine)
    if action in ("close", "tutup"):
        await s.close()
        pool.sessions.pop(key, None)
        return "Browser ditutup."
    return "action tidak dikenal. Pilihan: open, click, type, submit, read, back, close."

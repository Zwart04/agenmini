"""Bot Telegram (long polling: VPS tidak perlu membuka port untuk ini).

Privat: hanya chat yang sudah mengirim /kode <kode-pasangan> yang dilayani.
Token utama melayani semua bot (pindah dengan /bot); bot yang punya token sendiri tampil sebagai bot terpisah.
"""
import asyncio
import html
import json
import re
import time
import traceback

import aiohttp

from . import agent, db, hub, llm, memory
from .bench import pretty

API = "https://api.telegram.org/bot{token}/{method}"


def md_to_html(text: str) -> str:
    """Markdown sederhana → HTML Telegram."""
    parts = re.split(r"(```[\s\S]*?```)", text or "")
    out = []
    for p in parts:
        if p.startswith("```") and p.endswith("```"):
            body = re.sub(r"^```[\w-]*\n?", "", p)[:-3]
            out.append(f"<pre>{html.escape(body)}</pre>")
            continue
        s = html.escape(p)
        s = re.sub(r"^(\s*)[-*]\s+", r"\1• ", s, flags=re.M)  # daftar "- x" → "• x"
        s = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", s)
        s = re.sub(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", s, flags=re.M)
        out.append(s)
    return "".join(out)


def friendly(text: str) -> str:
    """Nama alat (web_search) → nama ramah (Mencari di web) untuk tampilan."""
    from .tools import REGISTRY
    for t in REGISTRY.values():
        text = text.replace(t.name, t.label)
    return re.sub(r"(\d)\s*-\s*(\d)", r"\1 sampai \2", text)


def split_text(text: str, n: int = 3800) -> list[str]:
    chunks = []
    while len(text) > n:
        cut = text.rfind("\n", 0, n)
        cut = cut if cut > n // 2 else n
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)
    return chunks


def _ids(key: str) -> set[str]:
    try:
        return {str(x).strip() for x in json.loads(db.setting(key) or "[]") if str(x).strip()}
    except Exception:
        return set()


def allowed() -> set[str]:
    """Chat yang terhubung lewat /kode (cara cadangan)."""
    return _ids("tg_allowed")


def user_ids() -> set[str]:
    """User ID Telegram yang boleh memakai semua bot (didapat dari @userinfobot)."""
    return _ids("tg_user_ids")


def find_bot(q: str) -> dict | None:
    """Cari bot dari id atau namanya (tidak peka huruf besar/kecil)."""
    q = (q or "").strip().lower()
    return db.bot(q) or next((b for b in db.bots() if b["name"].lower() == q), None)


def is_allowed(user_id, chat_id) -> bool:
    return str(user_id) in user_ids() or str(chat_id) in allowed()


class TgBot:
    def __init__(self, token: str, fixed_bot: str | None = None):
        self.token = token
        self.fixed_bot = fixed_bot  # None = token utama
        self.offset = 0
        self.locks: dict[str, asyncio.Lock] = {}
        self.me = {}
        self.stopped = False

    async def call(self, method: str, **params):
        params = {k: v for k, v in params.items() if v is not None}
        for attempt in range(3):
            try:
                async with llm.session().post(API.format(token=self.token, method=method), json=params,
                                              timeout=aiohttp.ClientTimeout(total=70)) as r:
                    data = await r.json(content_type=None)
                if data.get("ok"):
                    return data["result"]
                if data.get("error_code") == 429:
                    await asyncio.sleep(data.get("parameters", {}).get("retry_after", 3))
                    continue
                raise RuntimeError(data.get("description", "galat Telegram"))
            except aiohttp.ClientError:
                await asyncio.sleep(2)
        raise RuntimeError("Telegram tidak bisa dihubungi")

    async def send(self, chat_id, text: str, buttons=None, reply_to=None):
        last = None
        chunks = split_text(text)
        for i, c in enumerate(chunks):
            markup = {"inline_keyboard": buttons} if buttons and i == len(chunks) - 1 else None
            try:
                last = await self.call("sendMessage", chat_id=chat_id, text=md_to_html(c), parse_mode="HTML",
                                       reply_markup=markup, disable_web_page_preview=True, reply_to_message_id=reply_to)
            except RuntimeError:
                last = await self.call("sendMessage", chat_id=chat_id, text=c, reply_markup=markup,
                                       disable_web_page_preview=True)
        return last

    async def edit(self, chat_id, message_id, text: str, buttons=None, plain=False):
        markup = {"inline_keyboard": buttons} if buttons else None
        try:
            if plain:
                await self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text[:4000],
                                reply_markup=markup, disable_web_page_preview=True)
            else:
                await self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=md_to_html(text)[:4090],
                                parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except RuntimeError as e:
            if "not modified" in str(e):
                return
            if not plain:
                await self.edit(chat_id, message_id, text, buttons, plain=True)

    def bot_for_chat(self, chat_id) -> dict:
        if self.fixed_bot:
            return db.bot(self.fixed_bot)
        bid = db.setting(f"tg_bot:{chat_id}") or "asisten"
        return db.bot(bid) or db.bots(active_only=True)[0]

    # ---------- pembaruan masuk ----------

    async def poll(self):
        try:
            self.me = await self.call("getMe")
            await self.call("setMyCommands", commands=[
                {"command": "bot", "description": "Daftar bot dan pindah bot"},
                {"command": "tokenbot", "description": "Beri bot akun Telegram sendiri"},
                {"command": "baru", "description": "Mulai percakapan baru"},
                {"command": "riwayat", "description": "Riwayat percakapan: lanjutkan atau unduh"},
                {"command": "ingatan", "description": "Lihat ingatan"},
                {"command": "skill", "description": "Lihat skill yang dipelajari"},
                {"command": "jadwal", "description": "Lihat jadwal"},
                {"command": "status", "description": "Status server & model"},
                {"command": "bantuan", "description": "Bantuan"},
            ])
        except Exception as e:
            print(f"[telegram] token tidak valid / tidak terhubung: {e}")
            return
        print(f"[telegram] aktif sebagai @{self.me.get('username')}")
        while not self.stopped:
            try:
                ups = await self.call("getUpdates", offset=self.offset, timeout=50,
                                      allowed_updates=["message", "callback_query"])
                for u in ups:
                    self.offset = u["update_id"] + 1
                    asyncio.create_task(self.handle(u))
            except Exception as e:
                if "Conflict" in str(e):
                    await asyncio.sleep(10)
                else:
                    await asyncio.sleep(5)

    async def handle(self, u: dict):
        try:
            if "callback_query" in u:
                await self.on_callback(u["callback_query"])
            elif "message" in u:
                await self.on_message(u["message"])
        except Exception:
            traceback.print_exc()

    async def on_message(self, m: dict):
        chat_id = str(m["chat"]["id"])
        uid = str((m.get("from") or {}).get("id", ""))
        text = (m.get("text") or m.get("caption") or "").strip()
        if not is_allowed(uid, chat_id):
            code = db.setting("pair_code")
            if text.startswith("/kode") and code and text.split()[-1] == code:
                db.set_setting("tg_user_ids", json.dumps(sorted(user_ids() | {uid})))
                await self.send(chat_id, f"Terhubung. User ID {uid} sekarang diizinkan. Ketik /bantuan untuk mulai.")
            else:
                await self.send(chat_id, (
                    f"Bot ini privat.\n\nUser ID Telegram Anda: `{uid}`\n"
                    "Kalau Anda pemiliknya, masukkan User ID ini di web (menu Pengaturan, bagian Telegram), "
                    "atau jalankan di VPS: agen izinkan " + uid))
            return
        pending = db.setting(f"tg_correction:{chat_id}")
        if pending and text and not text.startswith("/"):
            await agent.feedback(int(pending), False, text)
            db.set_setting(f"tg_correction:{chat_id}", "")
            await self.send(chat_id, "Koreksi tersimpan dan akan dipakai pada tugas berikutnya. Ini tidak mengubah bobot model.")
            return
        images = []
        file_id = None
        if m.get("photo"):
            file_id = m["photo"][-1]["file_id"]  # ukuran terbesar
        elif (m.get("document") or {}).get("mime_type", "").startswith("image/"):
            file_id = m["document"]["file_id"]
        if file_id:
            try:
                images.append(await self.download(file_id))
            except Exception as e:
                await self.send(chat_id, f"Gambar gagal diunduh dari Telegram: {e}")
                return
        elif m.get("voice") or m.get("audio") or m.get("video") or m.get("video_note"):
            await self.send(chat_id, "Maaf, saya belum bisa mendengar suara atau menonton video. Kirim sebagai teks atau gambar ya.")
            return
        elif m.get("document"):
            await self.send(chat_id, "Untuk sekarang saya bisa membaca teks dan gambar. Berkas jenis ini belum bisa saya buka.")
            return
        if not text and not images:
            await self.send(chat_id, "Untuk sekarang saya bisa membaca teks dan gambar.")
            return
        if text.startswith("/") and not images:
            if await self.command(chat_id, text, m):
                return
        lock = self.locks.setdefault(chat_id, asyncio.Lock())
        if lock.locked():
            await self.send(chat_id, "Masih mengerjakan pesan sebelumnya, pesan ini masuk antrean.")
        async with lock:
            await self.run_turn(chat_id, text, images)

    async def download(self, file_id: str) -> bytes:
        info = await self.call("getFile", file_id=file_id)
        if info.get("file_size", 0) > 20_000_000:
            raise RuntimeError("gambar lebih dari 20 MB")
        url = f"https://api.telegram.org/file/bot{self.token}/{info['file_path']}"
        async with llm.session().get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                raise RuntimeError(f"status {r.status}")
            return await r.read()

    async def send_file(self, chat_id, rel_path: str, caption: str = ""):
        """Kirim berkas dari folder kerja: gambar sebagai foto, selain itu sebagai dokumen."""
        from . import vision
        path = vision.work_path(rel_path)
        is_img = path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif") and path.stat().st_size < 9_000_000
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if caption:
            form.add_field("caption", caption[:1000])
        form.add_field("photo" if is_img else "document", path.read_bytes(), filename=path.name)
        method = "sendPhoto" if is_img else "sendDocument"
        async with llm.session().post(API.format(token=self.token, method=method), data=form,
                                      timeout=aiohttp.ClientTimeout(total=120)) as r:
            data = await r.json(content_type=None)
        if not data.get("ok") and is_img:  # foto ditolak (mis. ukuran aneh): kirim sebagai dokumen
            form = aiohttp.FormData()
            form.add_field("chat_id", str(chat_id))
            form.add_field("document", path.read_bytes(), filename=path.name)
            async with llm.session().post(API.format(token=self.token, method="sendDocument"), data=form,
                                          timeout=aiohttp.ClientTimeout(total=120)) as r:
                data = await r.json(content_type=None)
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "gagal mengirim berkas"))

    async def send_bytes(self, chat_id, data: bytes, filename: str, caption: str = ""):
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if caption:
            form.add_field("caption", caption[:1000])
        form.add_field("document", data, filename=filename)
        async with llm.session().post(API.format(token=self.token, method="sendDocument"), data=form,
                                      timeout=aiohttp.ClientTimeout(total=60)) as r:
            await r.read()

    async def run_turn(self, chat_id: str, text: str, images: list | None = None):
        bot = self.bot_for_chat(chat_id)
        status_msg = await self.call("sendMessage", chat_id=chat_id, text=f"{bot['name']}: berpikir…")
        mid = status_msg["message_id"]
        state = {"status": "Berpikir…", "draft": "", "last_edit": 0.0, "done": False}

        async def typing():
            while not state["done"]:
                try:
                    await self.call("sendChatAction", chat_id=chat_id, action="typing")
                except Exception:
                    pass
                await asyncio.sleep(5)

        async def refresh(force=False):
            if time.time() - state["last_edit"] < (1.2 if force else 2.5):
                return
            state["last_edit"] = time.time()
            body = f"{bot['name']}: {state['status']}"
            if state["draft"]:
                body = state["draft"][-3500:] + " ▌"
            await self.edit(chat_id, mid, body, plain=True)

        async def on_event(kind, data):
            if kind == "status":
                state["status"], state["draft"] = data, ""
                await refresh(force=True)
            elif kind == "token":
                state["draft"] += data
                await refresh()
            elif kind == "approval":
                pass

        typer = asyncio.create_task(typing())
        try:
            res = await agent.Turn(bot, "tg", chat_id, on_event).run(text, images=images or None)
        finally:
            state["done"] = True
            typer.cancel()
        await self.finish(chat_id, mid, res)

    async def finish(self, chat_id, status_mid, res: dict):
        text = res.get("text", "")
        if res.get("approval"):
            buttons = [[{"text": "Izinkan", "callback_data": f"ap:{res['approval']}:1"},
                        {"text": "Tolak", "callback_data": f"ap:{res['approval']}:0"}]]
        elif res.get("message_id"):
            buttons = [[{"text": "Sesuai", "callback_data": f"fb:{res['message_id']}:1"},
                        {"text": "Koreksi", "callback_data": f"fb:{res['message_id']}:0"}],
                       [{"text": "Simpan cara kerja", "callback_data": f"learn:{res['message_id']}"}]]
        else:
            buttons = None
        if len(text) <= 3800:
            await self.edit(chat_id, status_mid, text, buttons)
        else:
            try:
                await self.call("deleteMessage", chat_id=chat_id, message_id=status_mid)
            except Exception:
                pass
            await self.send(chat_id, text, buttons)
        for rel in (res.get("meta") or {}).get("files") or []:
            try:
                await self.send_file(chat_id, rel)
            except Exception as e:
                await self.send(chat_id, f"Berkas {rel} gagal dikirim: {e}")

    async def on_callback(self, cq: dict):
        chat_id = str(cq["message"]["chat"]["id"])
        data = cq.get("data", "")
        if not is_allowed(cq.get("from", {}).get("id", ""), chat_id):
            await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Tidak diizinkan")
            return
        kind, _, rest = data.partition(":")
        if kind == "learn":
            message = await agent.save_verified_skill(int(rest))
            await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Prosedur ditinjau")
            await self.send(chat_id, message)
        elif kind == "fb":
            mid, good = rest.split(":")
            await agent.feedback(int(mid), good == "1")
            await self.call("answerCallbackQuery", callback_query_id=cq["id"],
                            text="Penilaian tersimpan." if good == "1" else "Kirim koreksinya sebagai pesan berikutnya.")
            if good != "1":
                db.set_setting(f"tg_correction:{chat_id}", mid)
                await self.send(chat_id, "Apa yang salah dan bagaimana jawaban yang benar? Kirim koreksi dalam pesan berikutnya, atau /batal untuk batal.")
            await self.call("editMessageReplyMarkup", chat_id=chat_id, message_id=cq["message"]["message_id"],
                            reply_markup={"inline_keyboard": []})
        elif kind == "ap":
            aid, ok = rest.split(":")
            await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Diizinkan" if ok == "1" else "Ditolak")
            await self.call("editMessageReplyMarkup", chat_id=chat_id, message_id=cq["message"]["message_id"],
                            reply_markup={"inline_keyboard": []})
            status = await self.call("sendMessage", chat_id=chat_id, text="Menjalankan…" if ok == "1" else "…")
            lock = self.locks.setdefault(chat_id, asyncio.Lock())
            async with lock:
                res = await agent.resolve_approval(int(aid), ok == "1")
            await self.finish(chat_id, status["message_id"], res)
        elif kind == "bot":
            db.set_setting(f"tg_bot:{chat_id}", rest)
            b = db.bot(rest)
            await self.call("answerCallbackQuery", callback_query_id=cq["id"], text=f"Sekarang: {b['name']}")
            await self.edit(chat_id, cq["message"]["message_id"], f"Sekarang Anda bicara dengan **{b['name']}**.")
        elif kind in ("buka", "unduh"):
            ch = db.one("SELECT * FROM chats WHERE id=?", (int(rest),))
            if not ch or ch["channel"] != "tg" or ch["ext_id"] != chat_id:  # hanya riwayat chat ini sendiri
                await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Riwayat tidak ditemukan")
                return
            if kind == "buka":
                db.open_chat(ch["id"])
                if not self.fixed_bot:
                    db.set_setting(f"tg_bot:{chat_id}", ch["bot_id"])
                await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Dilanjutkan")
                last = db.q("SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 2", (ch["id"],))
                recap = "\n".join(f"{'Anda' if r['role'] == 'user' else 'Bot'}: {r['content'][:200]}" for r in reversed(last))
                await self.send(chat_id, f"Melanjutkan **{ch['title'] or 'percakapan'}**.\n\n{recap}")
            else:
                await self.call("answerCallbackQuery", callback_query_id=cq["id"], text="Menyiapkan berkas…")
                name = re.sub(r"[^\w]+", "", (ch["title"] or "percakapan").lower())[:30] or "percakapan"
                await self.send_bytes(chat_id, db.export_chat(ch["id"]).encode(), f"{name}.md")

    # ---------- perintah ----------

    async def command(self, chat_id: str, text: str, m: dict | None = None) -> bool:
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        bot = self.bot_for_chat(chat_id)
        if cmd == "/batal":
            db.set_setting(f"tg_correction:{chat_id}", "")
            await self.send(chat_id, "Koreksi dibatalkan.")
            return
        if cmd in ("/start", "/bantuan", "/help"):
            await self.send(chat_id, (
                f"Halo! Anda sedang bicara dengan **{bot['name']}**.\n\n"
                "Tulis saja permintaan Anda, misalnya:\n"
                "• cari harga emas hari ini\n• ingatkan saya rapat besok jam 9\n"
                "• buatkan bot yang tiap pagi merangkum berita teknologi\n\n"
                "**Perintah**\n"
                "/bot  daftar bot dan pindah bot\n/baru  percakapan baru\n/riwayat  lanjutkan atau unduh percakapan lama\n"
                "/ingatan  isi ingatan\n"
                "/skill  skill yang sudah dipelajari\n/jadwal  jadwal aktif\n/status  kondisi server\n\n"
                "**Bot dengan akun Telegram sendiri**\n"
                "1. Buat bot baru di @BotFather, salin tokennya\n"
                "2. Kirim: /tokenbot namabot token\n"
                "3. Bot itu langsung aktif sebagai akun Telegram terpisah\n"
                "Lepas lagi dengan /lepastoken namabot\n\n"
                "Di bawah jawaban ada tombol Bagus dan Kurang tepat. Penilaian Anda dipakai agen untuk belajar."))
            return True
        if cmd == "/bot":
            akun = {t.fixed_bot: t.me.get("username") for t in _running.values() if t.fixed_bot}
            lines = []
            for b in db.bots(active_only=True):
                where = f"@{akun[b['id']]}" if akun.get(b["id"]) else "lewat bot ini"
                lines.append(f"• **{b['name']}** (nama: {b['id']}), {where}")
            if self.fixed_bot:
                await self.send(chat_id, f"Bot ini khusus **{bot['name']}**.\n\nSemua bot:\n" + "\n".join(lines))
                return True
            rows = [[{"text": f"{b['name']}" + (" (aktif)" if b["id"] == bot["id"] else ""),
                      "callback_data": f"bot:{b['id']}"}] for b in db.bots(active_only=True)]
            await self.send(chat_id, "**Semua bot**\n" + "\n".join(lines) + "\n\nPilih bot untuk diajak bicara di sini:", rows)
            return True
        if cmd == "/tokenbot":
            if m:  # token itu rahasia: hapus pesannya dari riwayat chat
                try:
                    await self.call("deleteMessage", chat_id=chat_id, message_id=m["message_id"])
                except Exception:
                    pass
            if len(parts) < 3:
                await self.send(chat_id, "Cara pakai: /tokenbot namabot token\nContoh: /tokenbot riset 123456:ABC…\nLihat nama bot dengan /bot.")
                return True
            target = find_bot(parts[1])
            if not target:
                await self.send(chat_id, f"Bot '{parts[1]}' tidak ada. Lihat daftar nama dengan /bot.")
                return True
            token = parts[2].strip()
            if token == db.setting("telegram_token"):
                await self.send(chat_id, "Itu token bot utama. Buat bot baru di @BotFather untuk token terpisah.")
                return True
            try:
                async with llm.session().get(API.format(token=token, method="getMe"),
                                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                    info = await r.json(content_type=None)
                if not info.get("ok"):
                    raise RuntimeError(info.get("description", "token ditolak"))
            except Exception as e:
                await self.send(chat_id, f"Token tidak valid: {e}")
                return True
            db.save_bot({"id": target["id"], "telegram_token": token})
            await sync()
            await self.send(chat_id, f"Selesai. **{target['name']}** sekarang aktif sebagai @{info['result']['username']}. "
                                     "Buka bot itu lalu kirim /start.")
            return True
        if cmd == "/lepastoken":
            target = find_bot(parts[1]) if len(parts) > 1 else None
            if not target:
                await self.send(chat_id, "Cara pakai: /lepastoken namabot")
                return True
            db.save_bot({"id": target["id"], "telegram_token": ""})
            await sync()
            await self.send(chat_id, f"**{target['name']}** tidak lagi punya akun Telegram sendiri. Tetap bisa dipakai lewat /bot di sini.")
            return True
        if cmd == "/baru":
            db.new_chat(bot["id"], "tg", chat_id)
            await self.send(chat_id, "Percakapan baru dimulai. Percakapan sebelumnya tersimpan di /riwayat.")
            return True
        if cmd == "/riwayat":
            rows = db.q("SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.chat_id=c.id) n FROM chats c "
                        "WHERE bot_id=? AND channel='tg' AND ext_id=? ORDER BY updated_at DESC LIMIT 10", (bot["id"], chat_id))
            rows = [r for r in rows if r["n"]]
            if not rows:
                await self.send(chat_id, "Belum ada riwayat percakapan.")
                return True
            lines, buttons = [], []
            for i, r in enumerate(rows, 1):
                when = time.strftime("%d/%m %H.%M", time.localtime(r["updated_at"] or 0))
                lines.append(f"{i}. **{r['title'] or 'Percakapan'}** ({when}, {r['n']} pesan)" + ("  (sedang aktif)" if not r["archived"] else ""))
                row = [{"text": f"{i}. Unduh", "callback_data": f"unduh:{r['id']}"}]
                if r["archived"]:
                    row.insert(0, {"text": f"{i}. Lanjutkan", "callback_data": f"buka:{r['id']}"})
                buttons.append(row)
            await self.send(chat_id, f"**Riwayat percakapan dengan {bot['name']}**\n" + "\n".join(lines), buttons)
            return True
        if cmd == "/ingatan":
            rows = db.q("SELECT * FROM memories ORDER BY id DESC LIMIT 20")
            await self.send(chat_id, "**Ingatan terbaru**\n" + ("\n".join(f"• {friendly(r['text'])}" for r in rows) or "(kosong)"))
            return True
        if cmd == "/skill":
            rows = db.q("SELECT * FROM skills WHERE active=1 ORDER BY updated_at DESC LIMIT 15")
            await self.send(chat_id, "**Skill yang sudah dipelajari**\n" + (
                "\n".join(f"• **{r['name']}** ({r['wins']} bagus, {r['fails']} kurang): {friendly(r['when_to_use'])}" for r in rows) or "(belum ada)"))
            return True
        if cmd == "/jadwal":
            from .tools import Ctx, list_schedules
            chat = db.chat_for(bot["id"], "tg", chat_id)
            await self.send(chat_id, "**Jadwal**\n" + await list_schedules(Ctx(bot, chat, "tg", chat_id)))
            return True
        if cmd == "/status":
            from .web import system_stats
            s = await system_stats()
            await self.send(chat_id, (
                f"RAM terpakai {s['ram_used_mb']} / {s['ram_total_mb']} MB (sisa {s['ram_available_mb']} MB)\n"
                f"CPU load: {s['load']}\nDisk sisa: {s['disk_free_gb']} GB\n"
                f"Model: {pretty(s['model'])}\nDi RAM: {', '.join(pretty(x.split(' (')[0]) for x in s['loaded']) or 'belum dimuat'}\n"
                f"Antrean: {s['queue']}"))
            return True
        return False


_running: dict[str, TgBot] = {}


async def _send_via(bot: dict, chat_id: str, text: str):
    token = bot.get("telegram_token") or db.setting("telegram_token")
    tg = _running.get(token)
    if tg:
        await tg.send(chat_id, text)


async def sync():
    """Nyalakan/matikan poller sesuai token yang tersimpan. Dipanggil saat mulai dan setiap pengaturan berubah."""
    hub.telegram_sender = _send_via
    wanted: dict[str, str | None] = {}
    main = db.setting("telegram_token")
    if main:
        wanted[main] = None
    for b in db.bots(active_only=True):
        if b.get("telegram_token") and b["telegram_token"] != main:
            wanted[b["telegram_token"]] = b["id"]
    for token, tg in list(_running.items()):
        if token not in wanted:
            tg.stopped = True
            _running.pop(token)
    for token, fixed in wanted.items():
        if token not in _running:
            tg = TgBot(token, fixed)
            _running[token] = tg
            asyncio.create_task(tg.poll())


def status() -> list[dict]:
    return [{"username": t.me.get("username"), "bot": t.fixed_bot or "(utama)"} for t in _running.values()]

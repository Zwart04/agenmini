"""Uji fitur versi 0.2: riwayat percakapan, gambar masuk (penglihatan), penjaga halusinasi, kirim berkas."""
import asyncio
import io
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from app import agent, config, db, llm, main, telegram, tools, vision  # noqa: E402

main.bootstrap()


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    async def __call__(self, messages, tools=None, model=None, **kw):
        self.seen.append({"messages": [dict(m) for m in messages], "tools": [t["function"]["name"] for t in tools or []]})
        r = self.replies.pop(0) if self.replies else {"content": "selesai"}
        if isinstance(r, str):
            r = {"content": r}
        r.setdefault("tool_calls", [])
        r.setdefault("stats", {})
        return r


def call(name, **args):
    return {"content": "", "tool_calls": [{"name": name, "arguments": args}]}


def run(coro):
    return asyncio.run(coro)


def png_bytes(color=(200, 30, 30)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, "PNG")
    return buf.getvalue()


# ---------- riwayat ----------

def test_migration_from_v01_splits_old_conversations():
    path = os.path.join(tempfile.mkdtemp(), "lama.sqlite")
    c = sqlite3.connect(path, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE chats (id INTEGER PRIMARY KEY, bot_id TEXT, channel TEXT, ext_id TEXT, summary TEXT DEFAULT '',
        reset_at REAL DEFAULT 0, updated_at REAL, UNIQUE(bot_id, channel, ext_id));
      CREATE TABLE messages (id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, content TEXT, meta TEXT DEFAULT '{}',
        created_at REAL, feedback INTEGER DEFAULT 0);
      CREATE TABLE approvals (id INTEGER PRIMARY KEY, chat_id INTEGER);
      INSERT INTO chats VALUES (1, 'asisten', 'tg', '42', '', 150, 300);
      INSERT INTO messages(chat_id, role, content, created_at) VALUES
        (1, 'user', 'Harga emas hari ini?', 100), (1, 'assistant', 'Rp 1.987.000', 110),
        (1, 'user', 'Ingatkan rapat jam 9', 200), (1, 'assistant', 'Siap', 210);
    """)
    db._migrate(c)
    rows = c.execute("SELECT * FROM chats ORDER BY id").fetchall()
    assert len(rows) == 2
    active = [r for r in rows if not r["archived"]][0]
    old = [r for r in rows if r["archived"]][0]
    assert active["title"] == "Ingatkan rapat jam 9" and old["title"] == "Harga emas hari ini?"
    assert c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?", (old["id"],)).fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?", (active["id"],)).fetchone()[0] == 2
    db._migrate(c)  # dijalankan dua kali tetap aman
    assert c.execute("SELECT COUNT(*) FROM chats").fetchone()[0] == 2


def test_new_open_export_delete_chat():
    a = db.chat_for("asisten", "web", "h1")
    db.add_message(a["id"], "user", "Resep rendang padang yang enak")
    db.add_message(a["id"], "assistant", "Bahan: daging sapi 1 kg…")
    b = db.new_chat("asisten", "web", "h1")
    assert b["id"] != a["id"] and db.one("SELECT archived FROM chats WHERE id=?", (a["id"],))["archived"] == 1
    assert db.one("SELECT title FROM chats WHERE id=?", (a["id"],))["title"] == "Resep rendang padang yang enak"
    db.new_chat("asisten", "web", "h1")  # percakapan kosong tidak ditumpuk di riwayat
    assert db.one("SELECT COUNT(*) n FROM chats WHERE ext_id='h1'")["n"] == 2
    db.open_chat(a["id"])
    assert db.chat_for("asisten", "web", "h1")["id"] == a["id"]
    assert db.one("SELECT COUNT(*) n FROM chats WHERE ext_id='h1'")["n"] == 1  # yang kosong dibuang
    text = db.export_chat(a["id"])
    assert "# Resep rendang padang yang enak" in text and "daging sapi" in text and "**Anda**" in text
    db.delete_chat(a["id"])
    assert not db.q("SELECT 1 FROM messages WHERE chat_id=?", (a["id"],))


# ---------- gambar ----------

def test_no_image_means_no_guessing():
    fake = FakeLLM(["Gambar ini adalah screenshot website Davdigi."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "g1").run("jelaskan apa saja yang ada di gambar ini"))
    assert res["text"] == agent.NO_IMAGE_REPLY and fake.seen == []  # model tidak dipanggil sama sekali
    assert not agent.asks_about_image("buatkan gambar kucing lucu")
    assert agent.asks_about_image("foto ini isinya apa?")


def test_image_is_seen_by_vision_then_answered():
    async def fake_describe(data, question=""):
        return "Spanduk biru bertulisan 'Kopi GRATIS Yuk Mampir', gerobak kopi, beberapa orang."
    vision.describe = fake_describe
    fake = FakeLLM(["tidak dipakai"])
    llm.chat = fake
    # pertanyaan ringan: jawaban "mata" langsung dipakai, otak utama tidak dipanggil (hemat ±1,5 menit di CPU)
    res = run(agent.Turn(db.bot("asisten"), "web", "g2").run("jelaskan apa saja yang ada di gambar ini",
                                                                images=[png_bytes()]))
    assert "Kopi GRATIS Yuk Mampir" in res["text"] and res["meta"]["mode"] == "penglihatan" and fake.seen == []
    # butuh alat (cari di web): deskripsi diteruskan ke otak utama
    fake = FakeLLM(["Saya carikan dulu.", "Kopi Liong Bulan dijual Rp 15.000."])
    llm.chat = fake
    run(agent.Turn(db.bot("asisten"), "web", "g2b").run("cari harga kopi yang ada di gambar ini", images=[png_bytes()]))
    prompt = fake.seen[0]["messages"][-1]["content"]
    assert "[Isi gambar" in prompt and "Kopi GRATIS Yuk Mampir" in prompt and "bukan ditulis pengguna" in prompt
    chat = db.chat_for("asisten", "web", "g2")
    um = db.q("SELECT content, meta FROM messages WHERE chat_id=? AND role='user'", (chat["id"],))[0]
    meta = json.loads(um["meta"])
    assert meta["images"][0].startswith("unggahan/") and "Kopi GRATIS" in meta["image_desc"]
    assert vision.work_path(meta["images"][0]).is_file()
    # pertanyaan lanjutan tentang gambar yang sama: tidak ditolak penjaga, deskripsi ikut di riwayat
    fake = FakeLLM(["Warnanya biru."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "g2").run("warna spanduk di gambar tadi apa?"))
    assert res["text"] == "Warnanya biru."
    assert any("Kopi GRATIS Yuk Mampir" in m["content"] for m in fake.seen[0]["messages"])


def test_vision_unavailable_is_honest():
    async def no_vision(data, question=""):
        raise vision.VisionUnavailable("Model penglihatan belum siap. Unduh dulu di VPS: agen unduh qwen3.5:0.8b")
    vision.describe = no_vision
    fake = FakeLLM(["mengarang"])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "g3").run("ini apa?", images=[png_bytes()]))
    assert "belum siap" in res["text"] and fake.seen == []


# ---------- berkas ----------

def test_claimed_file_that_does_not_exist_is_caught():
    fake = FakeLLM(["Saya sudah membuat denah dan menyimpannya sebagai pixel_map.png.",
                    "Maaf, saya belum bisa membuat berkas itu."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "f1").run("tolong cek denah pixel farm"))
    assert res["text"] == "Maaf, saya belum bisa membuat berkas itu."
    assert "pixel_map.png tidak ada" in fake.seen[1]["messages"][-1]["content"]
    fake = FakeLLM(["Tersimpan di pixel_map.png.", "Tetap di pixel_map.png."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "f1").run("tolong cek lagi"))
    assert "tidak ditemukan" in res["text"]  # masih ngotot: diberi catatan jujur


def test_send_file_attaches_real_file():
    (config.WORK_DIR / "laporan").mkdir(parents=True, exist_ok=True)
    (config.WORK_DIR / "laporan" / "emas.csv").write_text("tanggal,harga\n29/09,1987000\n")
    fake = FakeLLM([call("send_file", path="laporan/emas.csv"), "Sudah saya kirim berkas emas.csv."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "f2").run("tolong kirim berkas laporan/emas.csv"))
    assert res["meta"]["files"] == ["laporan/emas.csv"] and "tidak ditemukan" not in res["text"]
    fake = FakeLLM([call("send_file", path="tidakada.png"), "Maaf, berkasnya tidak ada."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "f3").run("kirim berkas tidakada.png"))
    assert res["meta"]["files"] == [] and "Error" in fake.seen[1]["messages"][-1]["content"]


def test_chart_made_by_python_is_sent_automatically():
    code = ("import matplotlib.pyplot as plt\nplt.bar(['Jan','Feb','Mar'],[10,15,12])\n"
            "plt.savefig('grafik_uji.png', dpi=60)\nprint('ok')")
    fake = FakeLLM([call("run_python", code=code), "Grafiknya sudah jadi."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "c1").run("buat grafik batang Jan 10 Feb 15 Mar 12"))
    assert "grafik_uji.png" in res["meta"]["files"], res
    assert "otomatis dikirim" in fake.seen[1]["messages"][-1]["content"]
    assert (config.WORK_DIR / "grafik_uji.png").stat().st_size > 1000


def test_image_generation_intent_and_tool_available():
    names = tools.REGISTRY.keys()
    assert "generate_image" in names and "send_file" in names
    assert "generate_image" in db.bot("asisten")["tools"]
    found = [t for t, _ in agent.intents("buatkan gambar kucing oren lucu", db.bot("asisten")["tools"])]
    assert "generate_image" in found and not agent.is_light("buatkan gambar kucing oren lucu", db.bot("asisten")["tools"])


def test_seed_fix_business_memory_not_always_injected():
    assert not db.one("SELECT 1 FROM memories WHERE kind='profil' AND text LIKE 'Pemilik menjalankan Davdigi%'")


# ---------- Telegram ----------

def test_telegram_photo_goes_to_vision():
    db.set_setting("tg_user_ids", json.dumps(["7"]))
    got = {}

    class FakeTg(telegram.TgBot):
        async def download(self, file_id):
            got["file_id"] = file_id
            return png_bytes()

        async def run_turn(self, chat_id, text, images=None):
            got["text"], got["images"] = text, images

        async def send(self, chat_id, text, buttons=None, reply_to=None):
            got["sent"] = text

    tg = FakeTg("x")
    run(tg.on_message({"chat": {"id": 7}, "from": {"id": 7}, "caption": "jelaskan gambar ini",
                       "photo": [{"file_id": "kecil"}, {"file_id": "besar"}]}))
    assert got["file_id"] == "besar" and got["text"] == "jelaskan gambar ini" and len(got["images"]) == 1
    run(tg.on_message({"chat": {"id": 7}, "from": {"id": 7}, "voice": {"file_id": "v"}}))
    assert "belum bisa mendengar" in got["sent"]


def test_cpu_setting_threads():
    db.set_setting("cpu_hemat", "1")
    assert llm.threads_for(llm.PRIO_USER) == max(1, (os.cpu_count() or 2) - 1)
    assert llm.threads_for(llm.PRIO_BACKGROUND) == llm.threads_for(llm.PRIO_USER)  # sama: model tidak dimuat ulang
    db.set_setting("cpu_hemat", "0")
    assert llm.threads_for(llm.PRIO_USER) is None

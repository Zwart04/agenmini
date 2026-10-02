"""Uji loop agen dengan model tiruan (tanpa Ollama): alat, izin, memori, jadwal, Telegram-format."""
import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

from app import agent, config, db, llm, main, scheduler, telegram, tools  # noqa: E402

main.bootstrap()


class FakeLLM:
    """Mengembalikan jawaban berurutan; mencatat pesan yang diterima."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    async def __call__(self, messages, tools=None, model=None, on_token=None, prio=0, fmt=None, **kw):
        self.seen.append({"messages": [dict(m) for m in messages], "tools": [t["function"]["name"] for t in tools or []], "fmt": fmt})
        r = self.replies.pop(0) if self.replies else {"content": "selesai"}
        if isinstance(r, str):
            r = {"content": r}
        r.setdefault("tool_calls", [])
        r.setdefault("content", "")
        r.setdefault("stats", {})
        return r


def call(name, **args):
    return {"tool_calls": [{"name": name, "arguments": args}]}


def run(coro):
    return asyncio.run(coro)


def test_plain_answer_and_history():
    fake = FakeLLM(["Halo juga!"])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "t1").run("halo"))
    assert res["text"] == "Halo juga!"
    msgs = fake.seen[0]["messages"]
    assert msgs[0]["role"] == "system" and "Asisten" in msgs[0]["content"]
    assert msgs[-1]["content"].endswith("[Pesan]\nhalo")
    assert sum(1 for m in msgs if "halo" in m["content"]) == 1  # pesan tidak dobel


def test_tool_then_answer_and_untrusted_wrapper(monkeypatch=None):
    async def fake_search(query, n=5):
        return [{"title": "Emas", "url": "https://contoh.id", "snippet": "Rp 1.987.000"}]
    from app import browser
    browser.search = fake_search
    fake = FakeLLM([call("web_search", query="harga emas"), "Harga emas Rp 1.987.000."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "t2").run("harga emas?"))
    assert "1.987.000" in res["text"] and res["meta"]["tools"] == ["web_search"]
    tool_msg = fake.seen[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["content"].startswith("<untrusted_content>")


def test_tool_not_allowed_for_bot():
    fake = FakeLLM([call("run_shell", command="ls"), "Maaf."])
    llm.chat = fake
    run(agent.Turn(db.bot("pengingat"), "web", "t3").run("jalankan ls"))
    assert "not available" in fake.seen[1]["messages"][-1]["content"]


def test_repeat_call_is_blocked():
    fake = FakeLLM([call("recall", query="x"), call("recall", query="x"), "ok"])
    llm.chat = fake
    b = db.bot("asisten")
    b["tools"] = b["tools"] + ["recall"]
    run(agent.Turn(b, "web", "t4").run("ingat x?"))
    assert "already did exactly this" in fake.seen[2]["messages"][-1]["content"]


def test_danger_needs_approval_then_runs():
    fake = FakeLLM([call("run_shell", command="rm -rf /data/ruang-kerja/sampah")])
    llm.chat = fake
    res = run(agent.Turn(db.bot("teknisi"), "web", "t5").run("hapus folder sampah"))
    assert res.get("approval") and "izin" in res["text"].lower()
    ran = {}

    async def fake_shell(ctx, command="", **_):
        ran["cmd"] = command
        return "[kode keluar 0]"
    tools.REGISTRY["run_shell"].fn = fake_shell
    llm.chat = FakeLLM(["Sudah dihapus."])
    res2 = run(agent.resolve_approval(res["approval"], True))
    assert ran["cmd"].startswith("rm -rf") and res2["text"] == "Sudah dihapus."
    again = run(agent.resolve_approval(res["approval"], True))
    assert "tidak berlaku" in again["text"]


def test_remember_rejects_invented_fact():
    fake = FakeLLM([call("remember", fact="Pemilik suka mendaki gunung"), "Oke."])
    llm.chat = fake
    run(agent.Turn(db.bot("asisten"), "web", "t6").run("catat: nama saya Sari"))
    assert "Tidak disimpan" in fake.seen[1]["messages"][-1]["content"]
    fake = FakeLLM([call("remember", fact="Pemilik bernama Sari"), "Oke, Sari."])
    llm.chat = fake
    run(agent.Turn(db.bot("asisten"), "web", "t6").run("tolong ingat, nama saya Sari"))
    assert db.one("SELECT 1 FROM memories WHERE text LIKE '%Sari%'")


def test_memory_injected_next_turn():
    fake = FakeLLM(["Anda Sari."])
    llm.chat = fake
    run(agent.Turn(db.bot("asisten"), "web", "t7").run("siapa nama saya Sari?"))
    assert "Sari" in fake.seen[0]["messages"][-1]["content"].split("[Pesan]")[0]


def test_reminder_job_delivers():
    ctx = tools.Ctx(db.bot("pengingat"), db.chat_for("pengingat", "web", "web"), "web", "web")
    out = run(tools.schedule(ctx, when="1 menit", message="minum air"))
    jid = int(out.split("#")[1].split(" ")[0])
    db.run("UPDATE jobs SET next_run=? WHERE id=?", (time.time() - 1, jid))
    job = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    run(scheduler.run_job(job))
    chat = db.chat_for("pengingat", "web", "web")
    last = db.q("SELECT content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1", (chat["id"],))[0]
    assert last["content"] == "Pengingat: minum air"
    assert db.one("SELECT active FROM jobs WHERE id=?", (jid,))["active"] == 0


def test_repeating_job_moves_forward():
    ctx = tools.Ctx(db.bot("pengingat"), db.chat_for("pengingat", "web", "web"), "web", "web")
    out = run(tools.schedule(ctx, when="07:00", message="cek", repeat="daily"))
    jid = int(out.split("#")[1].split(" ")[0])
    db.run("UPDATE jobs SET next_run=? WHERE id=?", (time.time() - 3 * 86400, jid))
    run(scheduler.run_job(db.one("SELECT * FROM jobs WHERE id=?", (jid,))))
    nxt = db.one("SELECT next_run, active FROM jobs WHERE id=?", (jid,))
    assert nxt["active"] == 1 and time.time() < nxt["next_run"] <= time.time() + 86400


def test_create_bot_tool():
    ctx = tools.Ctx(db.bot("asisten"), db.chat_for("asisten", "web", "web"), "web", "web")
    out = run(tools.create_bot(ctx, name="Resep", persona="Kamu koki.", tools="web_search, read_webpage, create_bot",
                               icon="heart"))
    b = db.bot("resep")
    assert b and b["icon"] == "heart" and "create_bot" not in b["tools"] and "web_search" in b["tools"]


def test_reflection_saves_skill_and_grounded_fact():
    from app import memory
    reply = {"content": json.dumps({"facts_about_user": ["Pemilik bernama Rudi.", "Pemilik suka kucing."],
                                    "success": True, "lesson": "",
                                    "skill": {"name": "Cari tiket lalu simpan", "when_to_use": "minta cari tiket dan simpan",
                                              "steps": ["Cari dengan web_search", "Simpan dengan write_file"]}})}
    llm.chat = FakeLLM([reply])
    turn = [{"role": "user", "content": "Nama saya Rudi, cari tiket Jakarta-Bali lalu simpan"}]
    res = run(memory.reflect(db.bot("asisten"), turn, ["web_search", "write_file"], feedback="Pemilik mengonfirmasi berhasil"))
    assert res["skill"] == "Cari tiket lalu simpan"
    assert res["facts"] == ["Pemilik bernama Rudi."]  # "suka kucing" tidak pernah diucapkan


def test_seed_skills_found_and_filtered_by_tools():
    from app import memory, seed
    assert seed.apply() == 0  # sudah dipasang saat bootstrap; tidak dobel
    asisten, pengingat = db.bot("asisten"), db.bot("pengingat")
    names = lambda b, q: [s["name"] for s in memory.search_skills(b, q)]  # noqa: E731
    assert names(asisten, "berapa harga emas antam sekarang?")[0] == "Cek harga emas hari ini"
    assert names(asisten, "cuaca di Bandung hari ini gimana")[0] == "Cek prakiraan cuaca"
    assert "Cek harga emas hari ini" not in names(asisten, "cuaca di Bandung hari ini")
    assert names(pengingat, "ingatkan saya minum obat besok jam 7")[0] == "Buat pengingat sekali"
    assert names(pengingat, "berapa harga emas antam") == []  # pengingat tidak punya web_search
    assert names(asisten, "tolong terjemahkan ke bahasa inggris")[0] == "Terjemahkan teks"
    assert names(asisten, "Apa ibu kota Australia?") == []  # "kota" saja tidak cukup untuk skill cuaca/sholat
    prof = [m["text"] for m in memory.profile_memories(asisten)]
    assert any("WIB" in t for t in prof)
    db.run("DELETE FROM skills WHERE name='Cari resep masakan'")
    seed.apply()
    assert not db.one("SELECT 1 FROM skills WHERE name='Cari resep masakan'")  # yang dihapus tidak kembali


T = ["web_search", "read_webpage", "run_python", "remember", "schedule", "write_file", "create_bot"]


def test_nudge_when_model_only_announces():
    assert agent.needs_nudge("Untuk itu, saya akan mencari data terkini melalui internet.", [], T)
    assert agent.needs_nudge("Saya menyimpan informasi bahwa nama kucing Anda Mochi.", [], T)
    assert agent.needs_nudge("Maaf, saya tidak memiliki akses data real-time.", [], T)
    assert not agent.needs_nudge("Ibu kota Jepang adalah Tokyo.", [], T, "Apa ibu kota Jepang?")
    assert not agent.needs_nudge("Saya akan mencari…", ["web_search"], T)
    # niat dari pesan pengguna: harga → web_search, ingat → remember, ingatkan → schedule, simpan berkas → write_file
    assert "web_search" in agent.needs_nudge("Harganya sekitar 1 juta.", [], T, "berapa harga emas antam hari ini?")
    assert "remember" in agent.needs_nudge("Baik!", [], T, "Tolong ingat ya, nama kucing saya Mochi.")
    assert "schedule" in agent.needs_nudge("Siap.", [], T, "Ingatkan saya minum obat besok jam 7")
    assert "write_file" in agent.needs_nudge("KRL pertama 04.00.", ["web_search"], T, "cari jadwal KRL lalu simpan ke berkas krl.txt")
    assert not agent.needs_nudge("Kamu tinggal di Bandung.", [], T, "apa kamu ingat saya tinggal di mana?")
    assert not agent.needs_nudge("Diskonnya Rp 30.000.", ["run_python"], T, "hitung harga setelah diskon 20% dari 150000")
    fake = FakeLLM(["Saya akan mencari harga emas dulu ya.", call("recall", query="emas"), "Rp 1.987.000"])
    llm.chat = fake
    b = db.bot("asisten")
    b["tools"] = [t for t in b["tools"] if t != "web_search"] + ["recall"]
    res = run(agent.Turn(b, "web", "t8").run("tolong cek emas antam"))  # 'cek' = bukan pertanyaan ringan
    assert res["text"] == "Rp 1.987.000" and fake.seen[1]["messages"][-1]["content"] == agent.NUDGE


def test_fast_path_for_light_questions():
    assert agent.is_light("Halo, selamat pagi! Apa kabar hari ini?", T)
    assert agent.is_light("Apa ibu kota Jepang?", T)
    assert agent.is_light("Terjemahkan ke bahasa Inggris: saya suka nasi goreng", T)
    assert not agent.is_light("berapa harga emas hari ini?", T)
    assert not agent.is_light("ringkas https://a.id/x", T)
    assert not agent.is_light("ingatkan saya rapat jam 9", T)
    fake = FakeLLM(["Tokyo."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "t9").run("Apa ibu kota Jepang?"))
    assert res["text"] == "Tokyo." and res["meta"]["mode"] == "cepat" and fake.seen[0]["tools"] == []
    # jawaban cepat yang ternyata butuh alat → naik ke jalur lengkap dengan alat
    fake = FakeLLM(["Maaf, saya tidak memiliki akses data real-time.", "Jawaban lengkap."])
    llm.chat = fake
    res = run(agent.Turn(db.bot("asisten"), "web", "t9").run("Siapa presiden Prancis?"))
    assert res["text"] == "Jawaban lengkap." and res["meta"]["mode"] == "lengkap" and fake.seen[1]["tools"]


def test_words_inside_link_are_not_intents():
    tools_found = [t for t, _ in agent.intents("Tolong ringkas https://contoh.id/berita/harga-emas", T)]
    assert tools_found == ["read_webpage"]
    assert not agent.needs_nudge("Ringkasan: banjir di Bekasi.", ["read_webpage"], T,
                                 "Tolong ringkas https://contoh.id/berita/banjir-bekasi")


def test_filler_removed_and_final_answer_requested():
    assert agent.clean_answer("Panggilan alat selesai. Harga emas Rp 1.987.000. [Search]") == "Harga emas Rp 1.987.000."
    assert agent.clean_answer("Web_search selesai.") == ""
    assert agent.clean_answer("Inflasi adalah kenaikan harga. [Search]") == "Inflasi adalah kenaikan harga."
    fake = FakeLLM([call("recall", query="emas"), "Web_search selesai.", "Harga emas Rp 1.987.000."])
    llm.chat = fake
    b = db.bot("asisten")
    b["tools"] = b["tools"] + ["recall"]
    res = run(agent.Turn(b, "web", "t10").run("tolong cek catatan emas saya"))
    assert res["text"] == "Harga emas Rp 1.987.000." and fake.seen[2]["messages"][-1]["content"] == agent.FINAL_PROMPT


def test_skill_synthesized_when_model_forgets():
    from app import memory
    llm.chat = FakeLLM([{"content": json.dumps({"facts_about_user": [], "success": True, "lesson": ""})}])
    turn = [{"role": "user", "content": "[Konteks]\nx\n\n[Pesan]\nCari jadwal KRL Bogor lalu simpan ke krl.txt"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "jadwal KRL Bogor"}}}]},
            {"role": "tool", "tool_name": "web_search", "content": "KRL pertama 04.00"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "krl.txt", "content": "04.00"}}}]},
            {"role": "tool", "tool_name": "write_file", "content": "Tersimpan"},
            {"role": "assistant", "content": "Sudah disimpan di krl.txt."}]
    res = run(memory.reflect(db.bot("asisten"), turn, ["web_search", "write_file"], feedback="Pemilik mengonfirmasi berhasil"))
    assert res["skill"] == "Cari jadwal KRL Bogor lalu simpan"
    sk = db.one("SELECT * FROM skills WHERE name=?", (res["skill"],))
    assert "web_search: jadwal KRL Bogor" in sk["steps"] and "write_file: krl.txt" in sk["steps"]


def test_clean_answer():
    assert agent.clean_answer("Harga naik — cukup tajam – kata _analis_.") == "Harga naik, cukup tajam, kata analis."
    assert agent.clean_answer("simpan di laporan_emas.md") == "simpan di laporan_emas.md"


def test_hints():
    assert "read_webpage" in agent.task_hints("ringkas https://a.id/x", ["read_webpage"])[0]
    assert agent.task_hints("ringkas https://a.id/x", ["web_search"]) == []
    assert "write_file" in agent.task_hints("cari lalu simpan ke berkas krl.txt", ["write_file"])[0]


def test_telegram_user_id_allowlist():
    db.set_setting("tg_user_ids", json.dumps(["111"]))
    db.set_setting("tg_allowed", json.dumps([]))
    assert telegram.is_allowed(111, 999) and telegram.is_allowed("111", "5")
    assert not telegram.is_allowed(222, 222)
    assert telegram.find_bot("Riset")["id"] == "riset" and telegram.find_bot("riset")["id"] == "riset"
    assert telegram.find_bot("tidakada") is None

    sent = []

    class FakeTg(telegram.TgBot):
        async def send(self, chat_id, text, buttons=None, reply_to=None):
            sent.append(text)

        async def call(self, method, **params):
            return {"message_id": 1}
    tg = FakeTg("x")
    run(tg.on_message({"chat": {"id": 222}, "from": {"id": 222}, "text": "halo"}))
    assert "Bot ini privat" in sent[-1] and "222" in sent[-1]
    code = db.setting("pair_code")
    run(tg.on_message({"chat": {"id": 222}, "from": {"id": 222}, "text": f"/kode {code}"}))
    assert telegram.is_allowed(222, 222) and "Terhubung" in sent[-1]


def test_telegram_markdown():
    h = telegram.md_to_html("**tebal** dan `kode` <b> [tautan](https://a.id)\n```\nx < y\n```")
    assert "<b>tebal</b>" in h and "<code>kode</code>" in h and "&lt;b&gt;" in h
    assert '<a href="https://a.id">tautan</a>' in h and "<pre>x &lt; y\n</pre>" in h
    parts = telegram.split_text("a\n" * 5000, 3800)
    assert all(len(p) <= 3800 for p in parts) and "".join(parts).count("a") == 5000

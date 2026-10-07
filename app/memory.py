"""Memori permanen dan self-improve.

- memories: fakta/preferensi/pelajaran. Dicari lewat FTS5 (tanpa model embedding, hemat RAM).
- skills: "catatan cara" hasil belajar dari tugas yang berhasil. Dipakai ulang saat tugas mirip.
- reflect(): fakta yang berdasar ucapan pemilik; skill melalui ledger bukti/review.
- consolidate(): perapian malam — gabung yang dobel, matikan skill yang sering gagal, perbaiki langkahnya.
"""
import json
import re
import time

from . import db, llm

STOP = set("""yang dan di ke dari ini itu untuk dengan pada adalah akan juga atau saya aku kamu anda tolong bisa
ada tidak apa bagaimana gimana mau ingin dong ya sih nya kan lagi sudah udah belum buat bikin cara kalau jika
hari sekarang cek berapa kapan dimana mana siapa minta diminta sebuah suatu misalnya contoh coba dulu
the a an of to in on for is are be and or with please""".split())


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w]+", (text or "").lower()) if len(w) > 2 and w not in STOP]


def fts_query(text: str) -> str:
    ws = list(dict.fromkeys(words(text)))[:12]
    return " OR ".join(f'"{w}"' for w in ws)


META_WORDS = {"pemilik", "pengguna", "user", "owner", "bernama", "namanya", "dia", "beliau", "memiliki", "mempunyai"}


def grounded(fact: str, source: str, need: float = 0.6) -> bool:
    """Fakta hanya boleh disimpan kalau kata-katanya memang ada di ucapan pengguna.
    Model kecil suka mengarang fakta; penyaring ini membuang yang tidak berdasar."""
    fw = [w for w in dict.fromkeys(words(fact)) if w not in META_WORDS]
    if not fw:
        return False
    src = set(words(source))
    hit = sum(1 for w in fw if w in src or any(w[:5] == s[:5] for s in src if len(w) > 5 and len(s) > 5))
    return hit / len(fw) >= need


def jaccard(a: str, b: str) -> float:
    sa, sb = set(words(a)), set(words(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def scopes_for(bot: dict) -> list[str]:
    return ["shared"] if bot.get("memory_scope", "shared") == "shared" else [bot["id"], "shared"]


# ---------- memori ----------

def search_memories(bot: dict, query: str, k: int = 5) -> list[dict]:
    fq = fts_query(query)
    if not fq:
        return []
    sc = scopes_for(bot)
    rows = db.q(
        f"SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.rowid WHERE memories_fts MATCH ? "
        f"AND m.kind!='bawaan_tidak_terverifikasi' AND m.scope IN ({','.join('?' * len(sc))}) ORDER BY bm25(memories_fts) LIMIT ?", (fq, *sc, k))
    now = time.time()
    for r in rows:
        db.run("UPDATE memories SET uses=uses+1, last_used=? WHERE id=?", (now, r["id"]))
    return rows


def profile_memories(bot: dict, k: int = 6) -> list[dict]:
    """Fakta inti tentang pemilik selalu disertakan, apa pun pertanyaannya."""
    sc = scopes_for(bot)
    return db.q(f"SELECT * FROM memories WHERE kind='profil' AND scope IN ({','.join('?' * len(sc))}) "
                f"ORDER BY uses DESC, id DESC LIMIT ?", (*sc, k))


def add_memory(scope: str, kind: str, text: str) -> tuple[int, bool]:
    """Simpan; kalau hampir sama dengan yang ada, perbarui saja. Kembalikan (id, baru?)."""
    from .learning import SECRET
    text = SECRET.sub("[rahasia dihapus]", (text or "").strip())
    if len(text) < 4:
        return 0, False
    fq = fts_query(text)
    if fq:
        for r in db.q("SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.rowid WHERE memories_fts MATCH ? "
                      "AND m.scope=? ORDER BY bm25(memories_fts) LIMIT 5", (fq, scope)):
            if jaccard(r["text"], text) >= 0.6:
                if len(text) > len(r["text"]):
                    db.run("UPDATE memories SET text=?, last_used=? WHERE id=?", (text, time.time(), r["id"]))
                return r["id"], False
    return db.run("INSERT INTO memories(scope,kind,text,created_at,last_used) VALUES(?,?,?,?,?)",
                  (scope, kind, text, time.time(), time.time())), True


# ---------- skill ----------

def search_skills(bot: dict, query: str, k: int = 2) -> list[dict]:
    fq = fts_query(query)
    if not fq:
        return []
    sc = [bot["id"], "shared"]
    rows = db.q(
        f"SELECT s.* FROM skills_fts f JOIN skills s ON s.id=f.rowid WHERE skills_fts MATCH ? AND s.active=1 "
        f"AND s.scope IN ({','.join('?' * len(sc))}) ORDER BY bm25(skills_fts) LIMIT 12", (fq, *sc))
    qw = set(words(query))
    from .tools import REGISTRY
    have = set(bot.get("tools", []))
    scored = []
    for rank, r in enumerate(rows):
        # skill yang butuh alat yang tidak dimiliki bot ini jangan disodorkan
        needs = {t for t in REGISTRY if re.search(rf"\b{t}\b", r["steps"])}
        if needs - have:
            continue
        sw = set(words(r["name"] + " " + r["when_to_use"]))
        overlap = len(qw & sw)
        if overlap >= 2 or (overlap >= 1 and len(qw) <= 2):  # satu kata umum ("kota") tidak cukup
            scored.append((-overlap, rank, r))
    return [r for *_, r in sorted(scored)[:k]]


def save_skill(scope: str, name: str, when_to_use: str, steps, source: str = "belajar") -> tuple[int, bool]:
    if isinstance(steps, list):
        steps = "\n".join(f"{i + 1}. {str(s).strip()}" for i, s in enumerate(steps) if str(s).strip())
    name, when_to_use, steps = (name or "").strip()[:80], (when_to_use or "").strip()[:300], (steps or "").strip()[:1500]
    from .learning import SECRET
    if SECRET.search(name + "\n" + when_to_use + "\n" + steps):
        raise ValueError("Simpan kredensial di Koneksi, bukan di skill.")
    if not name or not steps or len(steps) < 10:
        return 0, False
    for r in db.q("SELECT * FROM skills WHERE scope=?", (scope,)):
        if r["name"].lower() == name.lower() or jaccard(r["name"] + " " + r["when_to_use"], name + " " + when_to_use) >= 0.6:
            if (when_to_use or r['when_to_use'],steps) != (r['when_to_use'],r['steps']):
                from . import learning
                learning.snapshot(r)
            db.run("UPDATE skills SET when_to_use=?, steps=?, updated_at=?, active=1 WHERE id=?",
                   (when_to_use or r["when_to_use"], steps, time.time(), r["id"]))
            return r["id"], False
    return db.run("INSERT INTO skills(scope,name,when_to_use,steps,created_at,updated_at,source) VALUES(?,?,?,?,?,?,?)",
                  (scope, name, when_to_use, steps, time.time(), time.time(), source)), True


def score_skills(skill_ids: list[int], good: bool):
    col = "wins" if good else "fails"
    for sid in skill_ids:
        db.run(f"UPDATE skills SET {col}={col}+1 WHERE id=?", (sid,))


# ---------- refleksi (self-improve) ----------

REFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "facts_about_user": {"type": "array", "items": {"type": "string"}},
        "success": {"type": "boolean"},
        "skill": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "when_to_use": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
            },
        },
        "lesson": {"type": "string"},
    },
    "required": ["facts_about_user", "success", "lesson"],
}

REFLECT_PROMPT = """You review what an AI assistant just did, so it can learn. Transcript:

{transcript}

Reply in short JSON (keep every string brief):
- facts_about_user: durable personal facts the USER explicitly stated about themselves (name, city, job, family, preferences). Write each as a short sentence starting with "Pemilik", e.g. "Pemilik bernama Rudi." Never include questions, wishes or things the assistant said. Empty list if none.
- success: did the assistant complete the user's request correctly?
- skill: if success is true AND the assistant called 2 or more tools, you MUST write a reusable skill: a short name, when_to_use (one sentence describing that kind of request), and steps (2-6 short imperative steps, each naming the tool used, e.g. "web_search: ..."). If fewer than 2 tools were used, omit it.
- lesson: if something went wrong or was slow, one sentence on what to do differently next time; else empty string.
Write names, sentences and steps in Indonesian."""


def transcript_of(messages: list[dict], limit: int = 5000) -> str:
    out = []
    for m in messages:
        if m["role"] == "tool":
            out.append(f"[hasil {m.get('tool_name', 'alat')}] {m['content'][:400]}")
        elif m.get("tool_calls"):
            for c in m["tool_calls"]:
                out.append(f"ASSISTANT memanggil {c['function']['name']}({json.dumps(c['function']['arguments'], ensure_ascii=False)[:200]})")
        elif m["role"] in ("user", "assistant"):
            out.append(f"{m['role'].upper()}: {m['content'][:800]}")
    text = "\n".join(out)
    return text[-limit:]


async def reflect(bot: dict, turn_messages: list[dict], tools_used: list[str], feedback: str = "") -> dict:
    if db.setting("self_improve") == "off":return {}
    tr = transcript_of(turn_messages)
    if feedback:
        tr += f"\n\nUSER FEEDBACK afterwards: {feedback}"
    try:
        res = await llm.chat([{"role": "user", "content": REFLECT_PROMPT.format(transcript=tr)}],
                             fmt=REFLECT_SCHEMA, prio=llm.PRIO_BACKGROUND, temperature=0.1,
                             model=bot.get("model") or None, max_tokens=450)
        data = llm._loads(res["content"] or "{}")
        if not isinstance(data, dict):
            data = {}  # JSON rusak/terpotong: tetap lanjut, skill disusun dari urutan alat
    except llm.LLMError:
        return {}
    result = {"facts": [], "skill": None, "lesson": ""}
    scope = bot["id"] if bot.get("memory_scope") == "own" else "shared"
    # hanya ucapan pengguna sendiri (bagian setelah [Pesan]), bukan konteks yang disisipkan agen
    user_text = " ".join(m["content"].split("[Pesan]")[-1] for m in turn_messages
                         if m["role"] == "user" and not m["content"].startswith(("Kamu belum", "Sekarang tulis")))
    for f in (data.get("facts_about_user") or [])[:5]:
        if isinstance(f, str) and 6 < len(f) < 300 and grounded(f, user_text):
            _, new = add_memory(scope, "profil", f)
            if new:
                result["facts"].append(f)
    # Procedural learning goes through the evidence/review ledger in learning.py.
    # A model's self-assessed success must never activate an unreviewed skill here.
    # Lessons come from explicit owner corrections, not model guesses after a negative rating.
    return result


def synth_skill(turn_messages: list[dict], user_text: str) -> dict | None:
    """Susun skill dari urutan alat yang benar-benar dipakai (dipakai bila model lupa menulisnya)."""
    steps = []
    for m in turn_messages:
        for c in m.get("tool_calls") or []:
            name, args = c["function"]["name"], c["function"].get("arguments") or {}
            key = next((args[k] for k in ("query", "url", "path", "when", "message", "code", "command", "fact", "action")
                        if args.get(k)), "")
            steps.append(f"{name}: {str(key).strip()[:80]}" if key else name)
    steps = list(dict.fromkeys(steps))
    if len({s.split(':')[0] for s in steps}) < 2:
        return None
    steps.append("Jawab pengguna langsung dengan hasilnya, singkat, sebut sumbernya bila ada")
    req = re.sub(r"\s+", " ", user_text).strip()
    name = " ".join(req.split()[:6]).rstrip("?.!,")
    return {"name": name[:1].upper() + name[1:], "when_to_use": f"permintaan mirip: {req[:160]}", "steps": steps}


PERSONAL_HINT = re.compile(r"\b(nama (saya|aku|ku)|saya (tinggal|kerja|bekerja|suka|tidak suka|lahir|punya)|"
                           r"aku (tinggal|kerja|suka|punya)|panggil (saya|aku)|umur (saya|aku)|istri|suami|anak saya|"
                           r"hobi|alamat)\b", re.I)


def looks_personal(text: str) -> bool:
    return bool(PERSONAL_HINT.search(text or ""))


# ---------- perapian malam ----------

FIX_SKILL_PROMPT = """This saved procedure ("skill") of an AI assistant keeps failing.
Skill name: {name}
When to use: {when}
Steps:
{steps}

Lessons learned recently:
{lessons}

Rewrite the steps so they work better. Reply JSON: {{"when_to_use": "...", "steps": ["...", "..."]}}. Indonesian."""


async def consolidate() -> dict:
    if db.setting("self_improve") == "off":return {}
    report = {"memori_digabung": 0, "skill_dimatikan": 0, "skill_diperbaiki": 0, "ringkasan_dibuang": 0}
    # 1) gabung memori yang hampir sama (per scope)
    for scope_row in db.q("SELECT DISTINCT scope FROM memories"):
        rows = db.q("SELECT * FROM memories WHERE scope=? ORDER BY id", (scope_row["scope"],))
        dead = set()
        for i, a in enumerate(rows):
            if a["id"] in dead:
                continue
            for b in rows[i + 1:]:
                if b["id"] in dead:
                    continue
                if jaccard(a["text"], b["text"]) >= 0.7:
                    keep, drop = (a, b) if len(a["text"]) >= len(b["text"]) else (b, a)
                    db.run("UPDATE memories SET uses=uses+? WHERE id=?", (drop["uses"], keep["id"]))
                    db.run("DELETE FROM memories WHERE id=?", (drop["id"],))
                    dead.add(drop["id"])
                    report["memori_digabung"] += 1
                    if drop is a:
                        break
    # 2) ringkasan lama yang tidak pernah dipakai 90 hari
    cutoff = time.time() - 90 * 86400
    n = db.q("SELECT COUNT(*) n FROM memories WHERE kind='ringkasan' AND last_used<?", (cutoff,))[0]["n"]
    db.run("DELETE FROM memories WHERE kind='ringkasan' AND last_used<?", (cutoff,))
    report["ringkasan_dibuang"] = n
    # 3) skill yang lebih sering gagal: perbaiki sekali, kalau masih gagal matikan
    for s in db.q("SELECT * FROM skills WHERE active=1 AND fails>=2 AND fails>wins"):
        if s["fails"] >= s["wins"] + 4:
            db.run("UPDATE skills SET active=0 WHERE id=?", (s["id"],))
            report["skill_dimatikan"] += 1
            continue
        # A model rewrite is an untested hypothesis, not a repaired procedure.
        # Keep failed evidence and owner-edited versions; do not silently overwrite skills.
    return report


SUMMARY_PROMPT = """Summarize this conversation in Indonesian in at most 6 short bullet points. Keep names, numbers, decisions, and open tasks. Previous summary (merge it in):
{old}

Conversation:
{conv}"""


async def summarize_chat(chat_id: int, bot: dict, keep_last: int = 12):
    """Kalau percakapan panjang, pesan lama diringkas ke chats.summary supaya konteks tetap kecil."""
    chat = db.one("SELECT * FROM chats WHERE id=?", (chat_id,))
    rows = db.q("SELECT * FROM messages WHERE chat_id=? AND created_at>? AND role IN ('user','assistant') ORDER BY id",
                (chat_id, chat["reset_at"]))
    if len(rows) <= keep_last + 8:
        return
    old = rows[:-keep_last]
    conv = "\n".join(f"{r['role']}: {r['content'][:500]}" for r in old)[-6000:]
    try:
        res = await llm.chat([{"role": "user", "content": SUMMARY_PROMPT.format(old=chat["summary"] or "-", conv=conv)}],
                             prio=llm.PRIO_BACKGROUND, temperature=0.1, model=bot.get("model") or None)
    except Exception:
        return
    summary = res["content"].strip()[:1500]
    if summary:
        # geser batas riwayat: pesan lama tetap tersimpan, tapi tidak lagi dimuat ke konteks
        db.run("UPDATE chats SET summary=?, reset_at=? WHERE id=?", (summary, old[-1]["created_at"], chat_id))

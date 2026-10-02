"""Satu berkas SQLite untuk semua: bot, percakapan, memori, skill, jadwal, izin, pengaturan."""
import json
import re
import sqlite3
import threading
import time
from datetime import datetime

from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS bots (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT DEFAULT 'bot',
  persona TEXT NOT NULL, tools TEXT NOT NULL DEFAULT '[]',
  memory_scope TEXT NOT NULL DEFAULT 'shared',
  telegram_token TEXT DEFAULT '', model TEXT DEFAULT '',
  created_at REAL, active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY, bot_id TEXT, channel TEXT, ext_id TEXT,
  summary TEXT DEFAULT '', reset_at REAL DEFAULT 0, updated_at REAL,
  title TEXT DEFAULT '', archived INTEGER DEFAULT 0, created_at REAL
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, content TEXT,
  meta TEXT DEFAULT '{}', created_at REAL, feedback INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY, scope TEXT, kind TEXT, text TEXT,
  created_at REAL, last_used REAL, uses INTEGER DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(text, content='memories', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text); END;
CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text); END;
CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE OF text ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text); END;

CREATE TABLE IF NOT EXISTS skills (
  id INTEGER PRIMARY KEY, scope TEXT, name TEXT, when_to_use TEXT, steps TEXT,
  created_at REAL, updated_at REAL, uses INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0, fails INTEGER DEFAULT 0, active INTEGER DEFAULT 1, source TEXT DEFAULT 'belajar'
);
CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(name, when_to_use, steps, content='skills', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS sk_ai AFTER INSERT ON skills BEGIN
  INSERT INTO skills_fts(rowid, name, when_to_use, steps) VALUES (new.id, new.name, new.when_to_use, new.steps); END;
CREATE TRIGGER IF NOT EXISTS sk_ad AFTER DELETE ON skills BEGIN
  INSERT INTO skills_fts(skills_fts, rowid, name, when_to_use, steps) VALUES('delete', old.id, old.name, old.when_to_use, old.steps); END;
CREATE TRIGGER IF NOT EXISTS sk_au AFTER UPDATE OF name, when_to_use, steps ON skills BEGIN
  INSERT INTO skills_fts(skills_fts, rowid, name, when_to_use, steps) VALUES('delete', old.id, old.name, old.when_to_use, old.steps);
  INSERT INTO skills_fts(rowid, name, when_to_use, steps) VALUES (new.id, new.name, new.when_to_use, new.steps); END;

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY, bot_id TEXT, channel TEXT, ext_id TEXT,
  kind TEXT, text TEXT, next_run REAL, repeat TEXT DEFAULT '',
  active INTEGER DEFAULT 1, last_result TEXT DEFAULT '', created_at REAL
);

CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY, chat_id INTEGER, bot_id TEXT, tool TEXT, args TEXT,
  reason TEXT, status TEXT DEFAULT 'menunggu', created_at REAL
);

CREATE TABLE IF NOT EXISTS bench (
  id INTEGER PRIMARY KEY, model TEXT, created_at REAL, score REAL, total INTEGER,
  avg_seconds REAL, tok_per_sec REAL, ram_mb REAL, detail TEXT
);
"""


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript(SCHEMA)
        _migrate(c)
        _conn = c
    return _conn


def _migrate(c: sqlite3.Connection):
    """Versi 0.1: satu baris chat per (bot, saluran, pengguna), "percakapan baru" hanya menyembunyikan pesan lama.
    Versi 0.2: tiap percakapan baris sendiri (riwayat). Pesan lama yang dulu tersembunyi dipulihkan jadi riwayat."""
    bot_cols = {r[1] for r in c.execute("PRAGMA table_info(bots)")}
    if bot_cols and "backend" not in bot_cols:
        c.execute("ALTER TABLE bots ADD COLUMN backend TEXT DEFAULT ''")
    cols = {r[1] for r in c.execute("PRAGMA table_info(chats)")}
    if "archived" not in cols:
        c.executescript("""
        BEGIN;
        ALTER TABLE chats RENAME TO chats_lama;
        CREATE TABLE chats (
          id INTEGER PRIMARY KEY, bot_id TEXT, channel TEXT, ext_id TEXT,
          summary TEXT DEFAULT '', reset_at REAL DEFAULT 0, updated_at REAL,
          title TEXT DEFAULT '', archived INTEGER DEFAULT 0, created_at REAL);
        INSERT INTO chats(id, bot_id, channel, ext_id, summary, reset_at, updated_at, created_at)
          SELECT id, bot_id, channel, ext_id, summary, reset_at, updated_at, updated_at FROM chats_lama;
        DROP TABLE chats_lama;
        COMMIT;
        """)
        # reset_at tanpa ringkasan = dulu ditekan "percakapan baru": pisahkan pesan sebelumnya jadi riwayat sendiri
        for ch in c.execute("SELECT * FROM chats WHERE reset_at>0 AND (summary IS NULL OR summary='')").fetchall():
            old = c.execute("SELECT MIN(created_at) a, MAX(created_at) b FROM messages WHERE chat_id=? AND created_at<=?",
                            (ch["id"], ch["reset_at"])).fetchone()
            if old["a"] is None:
                continue
            cur = c.execute("INSERT INTO chats(bot_id, channel, ext_id, updated_at, created_at, archived) VALUES(?,?,?,?,?,1)",
                            (ch["bot_id"], ch["channel"], ch["ext_id"], old["b"], old["a"]))
            c.execute("UPDATE messages SET chat_id=? WHERE chat_id=? AND created_at<=?", (cur.lastrowid, ch["id"], ch["reset_at"]))
            c.execute("UPDATE chats SET reset_at=0 WHERE id=?", (ch["id"],))
    c.execute("CREATE INDEX IF NOT EXISTS chats_aktif ON chats(bot_id, channel, ext_id, archived)")
    # judul dari pesan pertama pengguna
    for ch in c.execute("SELECT id FROM chats WHERE title IS NULL OR title=''").fetchall():
        m = c.execute("SELECT content FROM messages WHERE chat_id=? AND role='user' ORDER BY id LIMIT 1", (ch["id"],)).fetchone()
        if m:
            c.execute("UPDATE chats SET title=? WHERE id=?", (make_title(m["content"]), ch["id"]))


def make_title(text: str) -> str:
    t = " ".join((text or "").split())
    t = t.split("[Pesan]")[-1].strip() if "[Pesan]" in t else t
    return (t[:57] + "…") if len(t) > 60 else (t or "Percakapan")


def q(sql: str, args=()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql: str, args=()) -> dict | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def run(sql: str, args=()) -> int:
    with _lock:
        cur = conn().execute(sql, args)
        return cur.lastrowid


# ---------- pengaturan ----------

def setting(key: str) -> str:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    if row is not None:
        return row["value"]
    return config.DEFAULTS.get(key, "")


def set_setting(key: str, value: str):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


# ---------- bot ----------

def bots(active_only=False) -> list[dict]:
    rows = q("SELECT * FROM bots" + (" WHERE active=1" if active_only else "") + " ORDER BY created_at")
    for r in rows:
        r["tools"] = json.loads(r["tools"] or "[]")
    return rows


def bot(bot_id: str) -> dict | None:
    r = one("SELECT * FROM bots WHERE id=?", (bot_id,))
    if r:
        r["tools"] = json.loads(r["tools"] or "[]")
    return r


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30] or "bot"
    base, n = s, 2
    while one("SELECT id FROM bots WHERE id=?", (s,)):
        s = f"{base}-{n}"
        n += 1
    return s


def save_bot(data: dict) -> str:
    bot_id = data.get("id") or slug(data["name"])
    existing = bot(bot_id)
    fields = {
        "name": data.get("name", existing["name"] if existing else bot_id),
        "icon": data.get("icon", existing["icon"] if existing else "bot"),
        "persona": data.get("persona", existing["persona"] if existing else ""),
        "tools": json.dumps(data.get("tools", existing["tools"] if existing else [])),
        "memory_scope": data.get("memory_scope", existing["memory_scope"] if existing else "shared"),
        "telegram_token": data.get("telegram_token", existing["telegram_token"] if existing else ""),
        "model": data.get("model", existing["model"] if existing else ""),
        "backend": data.get("backend", existing.get("backend", "") if existing else ""),
        "active": int(data.get("active", existing["active"] if existing else 1)),
    }
    if existing:
        run("UPDATE bots SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), bot_id))
    else:
        run("INSERT INTO bots(id,created_at," + ",".join(fields) + ") VALUES(?,?," + ",".join("?" * len(fields)) + ")",
            (bot_id, time.time(), *fields.values()))
    return bot_id


# ---------- percakapan ----------

def chat_for(bot_id: str, channel: str, ext_id: str) -> dict:
    """Percakapan yang sedang aktif untuk bot + saluran + pengguna ini (dibuat bila belum ada)."""
    key = (bot_id, channel, str(ext_id))
    row = one("SELECT * FROM chats WHERE bot_id=? AND channel=? AND ext_id=? AND archived=0 ORDER BY id DESC LIMIT 1", key)
    if row:
        return row
    now = time.time()
    cid = run("INSERT INTO chats(bot_id,channel,ext_id,updated_at,created_at) VALUES(?,?,?,?,?)", (*key, now, now))
    return one("SELECT * FROM chats WHERE id=?", (cid,))


def _archive_active(bot_id: str, channel: str, ext_id: str):
    """Pindahkan percakapan aktif ke riwayat. Percakapan kosong dibuang saja."""
    for ch in q("SELECT id FROM chats WHERE bot_id=? AND channel=? AND ext_id=? AND archived=0",
                (bot_id, channel, str(ext_id))):
        if one("SELECT 1 FROM messages WHERE chat_id=? LIMIT 1", (ch["id"],)):
            run("UPDATE chats SET archived=1 WHERE id=?", (ch["id"],))
        else:
            run("DELETE FROM chats WHERE id=?", (ch["id"],))


def new_chat(bot_id: str, channel: str, ext_id: str) -> dict:
    """Simpan percakapan aktif ke riwayat, lalu mulai yang baru."""
    _archive_active(bot_id, channel, ext_id)
    return chat_for(bot_id, channel, ext_id)


def open_chat(chat_id: int) -> dict | None:
    """Lanjutkan percakapan dari riwayat: jadikan aktif, yang sekarang aktif masuk riwayat."""
    ch = one("SELECT * FROM chats WHERE id=?", (chat_id,))
    if not ch:
        return None
    if ch["archived"]:
        _archive_active(ch["bot_id"], ch["channel"], ch["ext_id"])
        run("UPDATE chats SET archived=0, updated_at=? WHERE id=?", (time.time(), chat_id))
    return one("SELECT * FROM chats WHERE id=?", (chat_id,))


def export_chat(chat_id: int) -> str:
    """Percakapan sebagai teks Markdown (untuk diunduh)."""
    ch = one("SELECT * FROM chats WHERE id=?", (chat_id,))
    b = bot(ch["bot_id"]) if ch else None
    lines = [f"# {ch['title'] or 'Percakapan'}", "",
             f"Bot: {b['name'] if b else ch['bot_id']}  ",
             f"Saluran: {'Telegram' if ch['channel'] == 'tg' else 'Web'}  ",
             f"Dimulai: {datetime.fromtimestamp(ch['created_at'] or ch['updated_at'] or 0):%d/%m/%Y %H.%M}", ""]
    for m in q("SELECT * FROM messages WHERE chat_id=? AND role IN ('user','assistant') ORDER BY id", (chat_id,)):
        who = "Anda" if m["role"] == "user" else (b["name"] if b else "Bot")
        lines += [f"**{who}** ({datetime.fromtimestamp(m['created_at']):%d/%m %H.%M}):", "", m["content"], ""]
    return "\n".join(lines)


def delete_chat(chat_id: int):
    run("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    run("DELETE FROM approvals WHERE chat_id=?", (chat_id,))
    run("DELETE FROM chats WHERE id=?", (chat_id,))


def add_message(chat_id: int, role: str, content: str, meta: dict | None = None) -> int:
    run("UPDATE chats SET updated_at=? WHERE id=?", (time.time(), chat_id))
    if role == "user":
        run("UPDATE chats SET title=? WHERE id=? AND (title IS NULL OR title='')", (make_title(content), chat_id))
    return run("INSERT INTO messages(chat_id,role,content,meta,created_at) VALUES(?,?,?,?,?)",
               (chat_id, role, content, json.dumps(meta or {}, ensure_ascii=False), time.time()))


def history(chat_id: int, limit: int = 12) -> list[dict]:
    chat = one("SELECT reset_at FROM chats WHERE id=?", (chat_id,))
    rows = q("SELECT * FROM messages WHERE chat_id=? AND created_at>? AND role IN ('user','assistant') "
             "ORDER BY id DESC LIMIT ?", (chat_id, chat["reset_at"] if chat else 0, limit))
    rows.reverse()
    for r in rows:
        r["meta"] = json.loads(r["meta"] or "{}")
    return rows


HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
         "November", "Desember"]


def now_str() -> str:
    n = datetime.now().astimezone()
    return f"{HARI[n.weekday()]}, {n.day} {BULAN[n.month - 1]} {n.year} pukul {n:%H.%M} {n:%Z} ({n:%Y-%m-%d %H:%M})"

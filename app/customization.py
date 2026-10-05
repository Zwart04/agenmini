"""Owner-editable instructions and memory history. Security is enforced in code."""
import time
from . import db


def init():
    db.conn().execute('CREATE TABLE IF NOT EXISTS customization_versions (id INTEGER PRIMARY KEY, kind TEXT, target TEXT, content TEXT, created_at REAL)')


def snapshot(kind, target, content):
    init()
    db.run('INSERT INTO customization_versions(kind,target,content,created_at) VALUES(?,?,?,?)', (kind, str(target), content, time.time()))


def versions(kind, target):
    init()
    return db.q('SELECT * FROM customization_versions WHERE kind=? AND target=? ORDER BY id DESC LIMIT 50', (kind, str(target)))


def harness(text):
    if not isinstance(text, str) or len(text) > 12000:
        raise ValueError('Instruksi harus berupa teks, maksimal 12.000 karakter.')
    old = db.setting('custom_harness') or ''
    if old != text:
        snapshot('harness', 'shared', old)
        db.set_setting('custom_harness', text)


def edit_memory(mid, text):
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError('Ingatan harus berisi teks, maksimal 12.000 karakter.')
    old = db.one('SELECT * FROM memories WHERE id=?', (mid,))
    if not old:
        raise ValueError('Ingatan tidak ditemukan.')
    if old['text'] != text:
        snapshot('memory', mid, old['text'])
        db.run('UPDATE memories SET text=? WHERE id=?', (text, mid))


def restore(kind, target, version):
    init()
    row = db.one('SELECT * FROM customization_versions WHERE id=? AND kind=? AND target=?', (version, kind, str(target)))
    if not row:
        raise ValueError('Versi tidak ditemukan untuk catatan ini.')
    if kind == 'harness':
        harness(row['content'])
    elif kind == 'memory':
        edit_memory(int(target), row['content'])
    else:
        raise ValueError('Jenis versi tidak didukung.')

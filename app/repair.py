"""Durable AI change proposals. This module NEVER executes or installs generated code."""
import ast
import asyncio
import difflib
import hashlib
import io
import json
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from . import config, db, llm

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {'app/host_setup.py', 'app/harnesses.py', 'app/harness_stdio.py', 'app/repair.py', 'app/customization.py', 'app/control.py', 'app/config.py', 'app/db.py', 'app/guardrails.py', 'app/native_apps.py'}
tasks = {}
lock = asyncio.Lock()


def init():
    db.conn().execute('CREATE TABLE IF NOT EXISTS app_repairs (id TEXT PRIMARY KEY, prompt TEXT, bot TEXT, status TEXT, result TEXT DEFAULT "{}", error TEXT DEFAULT "", created_at REAL, updated_at REAL)')


def source_path(name):
    if not isinstance(name, str):
        raise ValueError('Jalur harus berupa teks.')
    p = PurePosixPath(name)
    if not isinstance(name, str) or '\\' in name or p.is_absolute() or '..' in p.parts or str(p) != name:
        raise ValueError('Jalur berkas tidak aman.')
    if name in PROTECTED or not ((name.startswith('app/') and p.suffix == '.py') or (name.startswith('frontend/') and p.suffix in ('.html', '.css', '.js'))):
        raise ValueError('Berkas di luar area edit. Penjaga, runtime, akun dan data tidak dapat diubah.')
    target = ROOT / name
    if not target.is_relative_to(ROOT) or any(parent.is_symlink() for parent in [target, *target.parents]):
        raise ValueError('Symlink tidak dapat diedit.')
    return target


def files():
    names = []
    for folder in ('app', 'frontend'):
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file():
                name = path.relative_to(ROOT).as_posix()
                try:
                    source_path(name)
                    if path.stat().st_size <= 100000:
                        names.append(name)
                except ValueError:
                    pass
    return names


def read_sources(names):
    if not isinstance(names, list) or not 1 <= len(names) <= 6 or not all(isinstance(n, str) for n in names) or len(set(names)) != len(names):
        raise ValueError('Pilih 1–6 berkas yang berbeda.')
    rows = []
    for name in names:
        path = source_path(name)
        if not path.is_file() or path.stat().st_size > 100000:
            raise ValueError('Berkas tidak ditemukan atau terlalu besar.')
        content = path.read_text(encoding='utf-8')
        rows.append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'content': content})
    if sum(len(r['content']) for r in rows) > 65000:
        raise ValueError('Pilihan terlalu besar. Bagi perubahan menjadi beberapa draft.')
    return rows


def validate(result, sources):
    if not isinstance(result, dict) or not isinstance(result.get('files'), list) or not 1 <= len(result['files']) <= len(sources):
        raise ValueError('Model tidak mengembalikan daftar berkas perubahan yang valid.')
    base = {r['path']: r for r in sources}
    rows, seen = [], set()
    for item in result['files']:
        name, content = item.get('path'), item.get('content')
        if name not in base or name in seen or not isinstance(content, str) or not content.strip() or len(content.encode()) > 120000:
            raise ValueError('Perubahan tidak cocok dengan pilihan berkas atau isinya tidak valid.')
        seen.add(name)
        path = source_path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != base[name]['sha256']:
            raise ValueError('Source berubah selama agen bekerja. Buat draft baru dari versi terbaru.')
        if name.endswith('.py'):
            ast.parse(content, filename=name)
        if content == base[name]['content']:
            continue
        diff = ''.join(difflib.unified_diff(base[name]['content'].splitlines(True), content.splitlines(True), fromfile='a/' + name, tofile='b/' + name))
        rows.append({'path': name, 'base_sha256': base[name]['sha256'], 'content': content, 'diff': diff})
    if not rows:
        raise ValueError('Model tidak menghasilkan perubahan.')
    return {'summary': str(result.get('summary', ''))[:2000], 'files': rows,
            'checks': 'Jalur, ukuran, hash source dan sintaks Python diperiksa. Belum menjalankan kode, tes integrasi atau review keamanan.',
            'deployment': 'Draft saja. Jalankan GitHub Actions pada Zwart04/agenmini sebelum memasang release. Aplikasi aktif tidak diubah.'}


async def generate(rid, sources):
    token = None
    try:
        row = db.one('SELECT * FROM app_repairs WHERE id=?', (rid,))
        bot = db.bot(row['bot'])
        if not bot:
            raise ValueError('Bot tidak ditemukan.')
        if bot.get('backend'):
            token = llm.backend_context.set(bot['backend'])
        db.run("UPDATE app_repairs SET status='generating',updated_at=? WHERE id=?", (time.time(), rid))
        messages = [{'role': 'system', 'content': 'You propose changes to Agen Mini without executing code. Return only JSON {"summary":"...","files":[{"path":"...","content":"complete replacement file"}]}. Edit only selected existing files. Preserve authentication, permissions, data, APIs and compatibility. Never include credentials or remove safety checks. If the requested feature needs other files, return files:[] and explain. No tool calls.'},
                    {'role': 'user', 'content': row['prompt'] + '\nSelected source:\n' + json.dumps(sources, ensure_ascii=False)}]
        response = await asyncio.wait_for(llm.chat(messages, model=bot.get('model') or None, max_tokens=10000, temperature=0.15), timeout=240)
        content = response.get('content', '').strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0]
        result = validate(json.loads(content), sources)
        result['model'] = response.get('stats', {})
        db.run("UPDATE app_repairs SET status='draft',result=?,updated_at=? WHERE id=?", (json.dumps(result, ensure_ascii=False), time.time(), rid))
    except asyncio.CancelledError:
        db.run("UPDATE app_repairs SET status='interrupted',error='Proses dihentikan; aplikasi aktif tidak berubah.',updated_at=? WHERE id=?", (time.time(), rid))
        raise
    except Exception as exc:
        # Provider errors can echo sensitive request headers; keep detailed traces out of artifacts.
        from .learning import SECRET
        error = SECRET.sub('[disamarkan]', str(exc))[:900] or type(exc).__name__
        db.run("UPDATE app_repairs SET status='failed',error=?,updated_at=? WHERE id=?", (error, time.time(), rid))
    finally:
        if token is not None:
            llm.backend_context.reset(token)
        tasks.pop(rid, None)


async def propose(prompt, names, bot='orchestrator'):
    if not isinstance(prompt, str) or not 5 <= len(prompt.strip()) <= 6000:
        raise ValueError('Tulis tujuan perubahan 5–6.000 karakter.')
    if not db.bot(bot):
        raise ValueError('Bot tidak ditemukan.')
    async with lock:
        init()
        for key in list(tasks):
            if tasks[key].done():
                tasks.pop(key, None)
        if tasks:
            raise ValueError('Satu draft sedang diproses. Tunggu atau batalkan dahulu.')
        sources = read_sources(names)
        rid = uuid.uuid4().hex
        db.run('INSERT INTO app_repairs(id,prompt,bot,status,created_at,updated_at) VALUES(?,?,?,"queued",?,?)', (rid, prompt, bot, time.time(), time.time()))
        tasks[rid] = asyncio.create_task(generate(rid, sources))
        return {'id': rid, 'status': 'queued', 'message': 'Usulan dibuat terpisah; aplikasi aktif tidak diubah.'}


def status():
    init()
    for row in db.q("SELECT id FROM app_repairs WHERE status IN ('queued','generating')"):
        if row['id'] not in tasks or tasks[row['id']].done():
            tasks.pop(row['id'], None)
            db.run("UPDATE app_repairs SET status='interrupted',error='Proses berhenti sebelum draft selesai; source aktif tidak berubah.' WHERE id=?", (row['id'],))
    rows = []
    for row in db.q('SELECT * FROM app_repairs ORDER BY created_at DESC LIMIT 20'):
        result = json.loads(row['result'])
        result['files'] = [{'path': f['path']} for f in result.get('files', [])]
        rows.append({**row, 'prompt': row['prompt'][:500], 'result': result})
    return rows


def detail(rid):
    init()
    row = db.one('SELECT * FROM app_repairs WHERE id=?', (rid,))
    if not row:
        raise ValueError('Draft tidak ditemukan.')
    return {**row, 'result': json.loads(row['result'])}


def archive(rid):
    init()
    row = db.one('SELECT * FROM app_repairs WHERE id=?', (rid,))
    if not row or row['status'] != 'draft':
        raise ValueError('Draft yang selesai tidak ditemukan.')
    result = json.loads(row['result'])
    for f in result['files']:
        path = source_path(f['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != f['base_sha256']:
            raise ValueError('Draft kedaluwarsa karena source telah berubah. Buat draft ulang.')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in result['files']:
            z.writestr('candidate/' + f['path'], f['content'])
        z.writestr('changes.diff', '\n'.join(f['diff'] for f in result['files']))
        z.writestr('manifest.json', json.dumps({'id': rid, 'files': [{'path': f['path'], 'base_sha256': f['base_sha256'], 'candidate_sha256': hashlib.sha256(f['content'].encode()).hexdigest()} for f in result['files']]}, indent=2))
        z.writestr('README.txt', 'DRAFT, BUKAN PEMASANG.\nTinjau changes.diff. Salin candidate ke branch terpisah Zwart04/agenmini (Windows atau Linux), bukan ke aplikasi aktif. Jalankan GitHub Actions Linux dan Windows, review keamanan, lalu buat release dengan workflow Publish. Pasang release yang lulus; installer menyimpan backup dan data lama. Untuk kembali default, pasang release stabil resmi. Jangan mengubah data/.env/model.\n')
    return out.getvalue()

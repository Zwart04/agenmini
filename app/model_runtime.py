"""Download a verified, text-only GGUF with persistent byte progress. Host invokes this CLI."""
import hashlib
import json
import os
import shutil
import time
import urllib.request
from . import config, local_models


def write_status(phase, message, **extra):
    path = config.DATA_DIR / 'runtime-status.json'
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps({'phase': phase, 'message': message, 'checked_at': time.time(), **extra}), encoding='utf-8')
    tmp.replace(path)


def valid(path, model):
    if not path.is_file() or path.stat().st_size != model['bytes']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as f:
        if f.read(4) != b'GGUF': return False
        f.seek(0)
        while chunk := f.read(4 * 1024 * 1024): digest.update(chunk)
    return digest.hexdigest() == model['sha256']


def download(model, opener=urllib.request.urlopen):
    cache = config.DATA_DIR / 'models'
    target = cache / model['id'] / model['file']
    target.parent.mkdir(parents=True, exist_ok=True)
    info = {'model_id': model['id'], 'total_bytes': model['bytes']}
    write_status('verifying', 'Memeriksa model yang sudah tersimpan.', **info)
    if valid(target, model):
        return target
    # Reuse the old llama.cpp HF cache; keep old models intact.
    old = cache / ('models--' + model['repo'].replace('/', '--')) / 'blobs' / model['sha256']
    if valid(old, model):
        os.link(old, target) if not target.exists() else shutil.copyfile(old, target)
        return target
    partial = target.with_suffix('.gguf.part')
    received = partial.stat().st_size if partial.exists() else 0
    if received >= model['bytes']:
        if valid(partial, model): partial.replace(target); return target
        partial.unlink(); received = 0
    if shutil.disk_usage(cache).free < model['bytes'] - received + 256 * 1024 * 1024:
        raise ValueError('Disk tidak cukup untuk model. Kosongkan ruang tanpa menghapus data aplikasi.')
    url = model.get("url") or f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['file']}"
    req = urllib.request.Request(url, headers={'Range': f'bytes={received}-'} if received else {})
    write_status('downloading', 'Mengunduh bobot model terverifikasi.', downloaded_bytes=received, **info)
    with opener(req, timeout=60) as response:
        if received and response.status == 206:
            if not response.headers.get('Content-Range', '').startswith(f'bytes {received}-'):
                raise ValueError('Posisi unduhan lanjutan tidak sesuai; coba kembali.')
        elif response.status == 200:
            received = 0
        else:
            raise ValueError('Server unduhan menolak berkas model.')
        last = 0
        with partial.open('ab' if received else 'wb') as f:
            while chunk := response.read(1024 * 1024):
                f.write(chunk); received += len(chunk)
                if received > model['bytes']: raise ValueError('Ukuran berkas model melebihi katalog.')
                if time.monotonic() - last > 1:
                    write_status('downloading', 'Mengunduh bobot model terverifikasi.', downloaded_bytes=received, **info)
                    last = time.monotonic()
    write_status('verifying', 'Memeriksa SHA256 model sebelum dipakai.', downloaded_bytes=received, **info)
    if not valid(partial, model):
        partial.unlink(missing_ok=True)
        raise ValueError('SHA256/ukuran model tidak cocok; unduhan gagal verifikasi. Coba kembali.')
    partial.replace(target)
    return target


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'plan':
        from . import db, chat_models
        mode=db.setting('llm_backend')
        engines={mode} | {b.get('backend') for b in db.bots(active_only=True)} | chat_models.engines()
        if 'auto' in engines:
            if db.setting('freellmapi_key'): engines.add('freellmapi')
            if db.setting('auto_local')=='1': engines.add('local')
            if db.setting('auto_9router')=='1': engines.add('router')
        print(json.dumps({'mode':mode, 'local':'local' in engines, 'router':bool(engines & {'router','compatible'}), 'free':'freellmapi' in engines, 'model':db.setting('local_model_id') or 'qwenpaw-2b'}))
        raise SystemExit(0)
    model = next((m for m in local_models.all_models() if m['id'] == sys.argv[1]), None)
    if not model: raise SystemExit(2)
    try:
        print(download(model))
    except Exception as exc:
        write_status('failed', 'Unduhan model gagal: ' + str(exc)[:300], model_id=model['id'])
        raise SystemExit(1)

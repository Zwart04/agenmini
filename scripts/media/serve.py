"""Run the real UI with disposable, explicitly labelled documentation data.

No model, Telegram, scheduler, or office worker is started. The gateway has no
accounts. Never point this script at an owner's DATA_DIR.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


async def serve(args, data, password, jwt):
    from app import db, main, web, config
    main.bootstrap(profile='template')
    db.set_setting('setup_complete', '1')
    db.set_setting('llm_backend', 'router')
    db.set_setting('office_idle_enabled', '0')
    chat = db.chat_for('orchestrator', 'web', 'web')
    db.add_message(chat['id'], 'user', 'Bantu saya menyiapkan alat konversi gambar. Saya ingin membaca kode dan meninjau hasilnya sebelum menjalankan.')
    db.add_message(chat['id'], 'assistant', '**Preview antarmuka · data demo**\n\nBerkas contoh tersedia di panel kerja. Ini rencana yang bisa kita tinjau:\n\n1. Pilih gambar dari komputer.\n2. Atur ukuran dan format keluaran.\n3. Uji hasil konversi, lalu unduh berkas.\n\nBuka **Panel kerja** untuk membaca `image-tools/export.js`. Percakapan ini adalah contoh dokumentasi, bukan hasil pengujian model.')
    source = '''// Berkas contoh dokumentasi — bukan keluaran model.
// Konversi gambar berjalan di browser pengguna.

export async function exportImage(source, options) {
  const { width = 1200, type = 'image/webp' } = options;
  const image = await createImageBitmap(source);
  const ratio = Math.min(1, width / image.width);
  const canvas = document.createElement('canvas');

  canvas.width = Math.round(image.width * ratio);
  canvas.height = Math.round(image.height * ratio);

  const context = canvas.getContext('2d');
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  image.close();

  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob);
      else reject(new Error('Gambar belum dapat diekspor.'));
    }, type, 0.9);
  });
}
'''
    project = config.WORK_DIR / 'image-tools'
    project.mkdir()
    (project / 'export.js').write_text(source, encoding='utf-8')
    (project / 'README.md').write_text('# Contoh dokumentasi\n\nBerkas contoh untuk preview panel kerja. Tidak dibuat oleh model.\n', encoding='utf-8')
    gateway_env = {**os.environ, 'DATA_DIR':str(data / 'gateway'), 'HOST':'127.0.0.1', 'PORT':str(args.gateway_port), 'JWT_SECRET':jwt, 'INITIAL_PASSWORD':password, 'API_KEY_SECRET':secrets.token_urlsafe(32), 'MACHINE_ID_SALT':secrets.token_urlsafe(32)}
    with (data / 'gateway.log').open('wb') as log:
        gateway = subprocess.Popen([str(args.gateway.resolve())], cwd=ROOT, env=gateway_env, stdout=log, stderr=subprocess.STDOUT)
        try:
            await web.start()
            ready = ROOT / '.local-tools/media-session.json'
            ready.write_text(json.dumps({'baseURL':f'http://127.0.0.1:{args.port}', 'password':password, 'fixture':True}))
            ready.chmod(0o600)
            print('Documentation preview ready; disposable data only.', flush=True)
            stop = asyncio.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)
            await stop.wait()
        finally:
            gateway.terminate()
            try:gateway.wait(timeout=10)
            except subprocess.TimeoutExpired:gateway.kill();gateway.wait()
            from app import llm
            if llm._session and not llm._session.closed:await llm._session.close()
            (ROOT / '.local-tools/media-session.json').unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', type=Path, required=True)
    parser.add_argument('--port', type=int, default=28772)
    parser.add_argument('--gateway-port', type=int, default=28773)
    args = parser.parse_args()
    (ROOT / '.local-tools').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='media-demo-', dir=ROOT / '.local-tools') as folder:
        data = Path(folder)
        password, jwt = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        (data / 'empty-home').mkdir()
        os.environ.update(DATA_DIR=str(data), AGEN_HOST_HOME=str(data / 'empty-home'), WEB_HOST='127.0.0.1', WEB_PORT_INTERNAL=str(args.port), WEB_TLS='0', WEB_PASSWORD=password, LLM_BACKEND='router', ROUTER_BASE=f'http://127.0.0.1:{args.gateway_port}', ROUTER_JWT_SECRET=jwt, AGENMINI_DESKTOP='1', TELEGRAM_TOKEN='')
        asyncio.run(serve(args, data, password, jwt))

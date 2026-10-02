"""Public HF GGUF and Ollama registry imports; metadata only until owner selects download."""
import hashlib
import json
import math
import re
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse
import aiohttp
from . import config, llm


def registry():
    try:
        rows = json.loads((config.DATA_DIR / 'custom-models.json').read_text(encoding='utf-8'))
        return [validate(m) for m in rows][:50]
    except FileNotFoundError: return []


def validate(m):
    if not re.fullmatch(r'custom-[a-f0-9]{16}', str(m.get('id', ''))): raise ValueError('ID model tidak valid.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.gguf', str(m.get('file', '')), re.I): raise ValueError('Nama GGUF tidak valid.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(m.get('sha256', ''))): raise ValueError('SHA256 model tidak tersedia.')
    url = urlparse(m.get('url', ''))
    if url.scheme != 'https' or url.netloc not in ('huggingface.co', 'registry.ollama.ai') or url.query or url.fragment:
        raise ValueError('Sumber unduhan model tidak valid.')
    size = int(m.get('bytes', 0))
    if not 1024 < size < 128 * 1024**3: raise ValueError('Ukuran model tidak didukung.')
    # Do not trust file-supplied memory estimates on subsequent reads.
    runtime = math.ceil(size / 1024**2) + 1200
    return {**m, 'bytes': size, 'runtime_mb': runtime, 'min_ram_gb': math.ceil((runtime + 900) / 1024),
            'download_gb': round(size / 1e9, 2), 'rank': 0, 'custom': True,
            'note': 'Model pilihan Anda; arsitektur dan kualitas belum diuji. SHA256 diperiksa sebelum dimuat.'}


async def metadata(url):
    async with llm.session().get(url, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False) as r:
        if r.status != 200: raise ValueError('Sumber tidak dapat dibaca. Gunakan model publik dan periksa nama/tag.')
        raw = bytearray()
        async for chunk in r.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw) > 8 * 1024 * 1024: raise ValueError('Metadata terlalu besar.')
        return json.loads(raw)


async def inspect(source, name):
    name = str(name).strip()
    if source == 'hf':
        name = name.removeprefix('https://huggingface.co/').rstrip('/')
        name = name.split('/resolve/')[0].split('/blob/')[0]
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) or '..' in name:
            raise ValueError('Isi repo Hugging Face: pemilik/nama-repo-GGUF.')
        data = await metadata('https://huggingface.co/api/models/' + name + '?blobs=true')
        rev = data.get('sha', '')
        if not re.fullmatch(r'[a-f0-9]{40}', rev): raise ValueError('Revisi model tidak dapat diverifikasi.')
        files = []
        for f in data.get('siblings', []):
            filename = f.get('rfilename', '')
            if not filename.lower().endswith('.gguf') or 'mmproj' in filename.lower() or re.search(r'-\d{5}-of-\d{5}', filename): continue
            if '..' in PurePosixPath(filename).parts: continue
            lfs = f.get('lfs') or {}
            if not re.fullmatch(r'[a-f0-9]{64}', str(lfs.get('sha256', ''))): continue
            files.append(make(name, filename, rev, lfs['size'], lfs['sha256'],
                              f'https://huggingface.co/{name}/resolve/{rev}/{quote(filename, safe="/")}', 'https://huggingface.co/' + name))
            if len(files) >= 50: break
        if not files: raise ValueError('Tidak ada GGUF tunggal dengan hash. Model split, privat, dan proyektor gambar belum didukung.')
        return files
    if source == 'ollama':
        name = name.removeprefix('ollama:').removeprefix('https://ollama.com/library/')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?(?::[A-Za-z0-9_.-]+)?', name) or '..' in name:
            raise ValueError('Isi nama Ollama, misalnya qwen3:0.6b.')
        repo, _, tag = name.partition(':'); tag = tag or 'latest'
        if '/' not in repo: repo = 'library/' + repo
        data = await metadata(f'https://registry.ollama.ai/v2/{repo}/manifests/{tag}')
        layers = [f for f in data.get('layers', []) if f.get('mediaType') == 'application/vnd.ollama.image.model']
        if len(layers) != 1: raise ValueError('Manifest tidak berisi satu bobot model yang didukung.')
        f = layers[0]; digest = f.get('digest', '').removeprefix('sha256:')
        return [make('ollama/' + repo, 'model.gguf', digest, f['size'], digest,
                     f'https://registry.ollama.ai/v2/{repo}/blobs/sha256:{digest}', 'https://ollama.com/' + repo)]
    raise ValueError('Pilih Hugging Face atau Ollama.')


def make(repo, file, rev, size, digest, url, source):
    return validate({'id': 'custom-' + hashlib.sha256(url.encode()).hexdigest()[:16], 'name': repo + ' · ' + file,
                     'repo': repo, 'file': PurePosixPath(file).name, 'original_file': file,
                     'revision': rev, 'bytes': size, 'sha256': digest, 'url': url, 'source': source})


def save(model):
    model = validate(model)
    rows = registry()
    rows = [m for m in rows if m['id'] != model['id']]
    if len(rows) >= 50: raise ValueError('Batas 50 model tambahan tercapai.')
    path = config.DATA_DIR / 'custom-models.json'; tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(rows + [model], ensure_ascii=False), encoding='utf-8')
    tmp.chmod(0o600); tmp.replace(path)
    return model

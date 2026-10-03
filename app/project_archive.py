"""Bounded project source archives with explicit omissions and no runtime data."""
import zipfile
from pathlib import Path

EXCLUDED_DIRECTORIES = {'.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '__pycache__', 'uploads'}
PRIVATE_SUFFIXES = {'.sqlite', '.sqlite3', '.db', '.log', '.gguf', '.pem', '.key', '.pyc'}
MAX_FILE_BYTES = 10_000_000
MAX_TOTAL_BYTES = 40_000_000


def create_source_zip(root, destination):
    import json
    root = Path(root)
    included = []
    omitted = []
    total = 0

    def walk(directory):
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            if path.is_symlink():
                omitted.append({'path': name, 'reason': 'symlink'})
            elif path.is_dir():
                if path.name in EXCLUDED_DIRECTORIES or path.name.startswith('.'):
                    omitted.append({'path': name + '/', 'reason': 'runtime, dependency or hidden directory'})
                else:
                    yield from walk(path)
            elif path.is_file():
                yield path

    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in walk(root):
            name = path.relative_to(root).as_posix()
            reason = None
            if path.name.startswith('.') or path.name.endswith(('-wal', '-shm')) or path.suffix in PRIVATE_SUFFIXES:
                reason = 'private or runtime file'
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                reason = 'file exceeds 10 MB'
            elif total + size > MAX_TOTAL_BYTES:
                reason = 'archive source exceeds 40 MB'
            if reason:
                omitted.append({'path': name, 'reason': reason})
                continue
            archive.write(path, name)
            included.append(name)
            total += size
        if not included:
            raise ValueError('Tidak ada source yang dapat diarsipkan; source asli tetap disimpan.')
        report = {'included_files': len(included), 'source_bytes': total, 'omitted': omitted,
                  'note': 'Source asli tetap ada di Workspace. Dependency, data runtime dan berkas yang melewati batas tidak disertakan.'}
        archive.writestr('AGENMINI-ARCHIVE.json', json.dumps(report, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():
            raise ValueError('ZIP proyek gagal CRC.')
    return report

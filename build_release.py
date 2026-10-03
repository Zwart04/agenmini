"""Build release assets from tracked source only, never installation data."""
import hashlib
import subprocess
import zipfile
from pathlib import Path
from build_installer import main, ROOT


def build():
    main()
    dist = ROOT / 'dist'
    installer = dist / 'pasang-vps.sh'
    checksum = dist / 'pasang-vps.sha256'
    checksum.write_text(hashlib.sha256(installer.read_bytes()).hexdigest() + '  pasang-vps.sh\n')
    with zipfile.ZipFile(dist / 'agenmini-vps.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(installer, installer.name)
        archive.write(checksum, checksum.name)
        archive.write(ROOT / 'CARA-PASANG-VPS.txt', 'CARA-PASANG-VPS.txt')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(dist / 'agenmini-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            if not name: continue
            if name == '.env' or name.startswith(('data/', 'dist/')): raise ValueError('Private/generated path is tracked: ' + name)
            archive.write(ROOT / name, 'agenmini/' + name)
    with zipfile.ZipFile(dist / 'agenmini-frontend.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            if name.startswith('frontend/'):
                archive.write(ROOT / name, name)
    for name in ('agenmini-vps.zip', 'agenmini-source.zip', 'agenmini-frontend.zip'):
        with zipfile.ZipFile(dist / name) as archive:
            assert archive.testzip() is None
    assets = ('pasang-vps.sh', 'agenmini-vps.zip', 'agenmini-source.zip', 'agenmini-frontend.zip')
    (dist / 'SHA256SUMS').write_text(''.join(hashlib.sha256((dist / n).read_bytes()).hexdigest() + '  ' + n + '\n' for n in assets))
    print('Release assets verified (ZIP CRC and SHA256).')


if __name__ == '__main__': build()

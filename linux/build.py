# SPDX-License-Identifier: GPL-3.0-or-later
"""Build native packages from one relocatable private Python payload, in CI."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def run(*args):subprocess.run([str(a) for a in args],check=True)


def copy_source(source,target):
    for path in source.rglob('*'):
        if path.is_symlink():raise ValueError('Source symlink rejected: '+str(path))
        if '__pycache__' in path.parts or path.suffix=='.pyc':continue
        if path.is_file():
            dest=target/path.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)


def archive_tree(root,dest,extra=None):
    with tarfile.open(dest,'w:gz' if dest.name.endswith('.gz') else 'w') as archive:
        if extra:
            info=tarfile.TarInfo('.PKGINFO');raw=extra.encode();info.size=len(raw);info.mode=0o644;archive.addfile(info,io.BytesIO(raw))
        for path in sorted(root.rglob('*')):
            if path.is_symlink() and (path.readlink().is_absolute() or not path.resolve().is_relative_to(root.resolve())):
                raise ValueError('Payload symlink leaves package: '+str(path))
            info=archive.gettarinfo(str(path),arcname=str(path.relative_to(root)))
            info.uid=info.gid=0;info.uname=info.gname='root'
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as data:archive.addfile(info,data)
            else:archive.addfile(info)


def build():
    parser=argparse.ArgumentParser();parser.add_argument('--gateway',type=Path,required=True);args=parser.parse_args()
    machine=platform.machine();arch={'x86_64':'amd64','aarch64':'arm64'}.get(machine)
    if not arch:raise SystemExit('Unsupported package architecture: '+machine)
    version=re.search(r'VERSION = "([0-9.]+)"',(ROOT/'app/__init__.py').read_text())[1]
    gateway=args.gateway.resolve()
    if not gateway.is_file() or gateway.is_symlink():raise ValueError('Gateway build missing')
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    scratch=ROOT/'.local-tools';scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-linux-',dir=scratch) as work:
        work=Path(work);managed=work/'managed-python'
        run('uv','python','install','--install-dir',managed,'--no-bin','--no-registry','3.12')
        found=Path(subprocess.check_output(['uv','python','find','--managed-python','--no-python-downloads','3.12'],env={**os.environ,'UV_PYTHON_INSTALL_DIR':str(managed)},text=True).strip()).resolve()
        if not found.is_relative_to(managed.resolve()) or not found.is_file():raise ValueError('uv interpreter leaves private staging directory')
        interpreter=found.parent.parent
        stage=work/'payload';app=stage/'opt/agenmini';app.mkdir(parents=True)
        shutil.copytree(interpreter,app/'runtime',symlinks=True)
        python=app/'runtime/bin/python3'
        if not python.resolve().is_relative_to(app.resolve()):raise ValueError('Private Python symlink leaves payload')
        # This override applies only to the copied, disposable private runtime.
        run('uv','pip','install','--python',python,'--break-system-packages','--python-platform',machine+'-manylinux_2_35','--only-binary=:all:','-r',ROOT/'requirements.lock')
        for folder in ('app','frontend'):copy_source(ROOT/folder,app/'server'/folder)
        for name in ('launcher.py','welcome.html'):shutil.copy2(ROOT/'linux'/name,app/name)
        for name in ('LICENSE','THIRD_PARTY_NOTICES.md','requirements.lock','README.md','CARA-PASANG-LINUX.md'):shutil.copy2(ROOT/name,app/name)
        copy_source(ROOT/'docs',app/'docs')
        (app/'bin').mkdir();shutil.copy2(gateway,app/'bin/agenmini-gateway');(app/'bin/agenmini-gateway').chmod(0o755)
        # Keep the gateway's upstream MIT terms alongside its binary.
        shutil.copy2(ROOT/'gateway/LICENSE',app/'bin/GATEWAY-LICENSE')
        for prefix in ('usr/bin','usr/share/applications','usr/share/icons/hicolor/256x256/apps','usr/share/licenses/agenmini'):
            (stage/prefix).mkdir(parents=True)
        shutil.copy2(ROOT/'linux/agenmini',stage/'usr/bin/agenmini');(stage/'usr/bin/agenmini').chmod(0o755)
        shutil.copy2(ROOT/'linux/agenmini.desktop',stage/'usr/share/applications/agenmini.desktop')
        shutil.copy2(ROOT/'frontend/mascot.png',stage/'usr/share/icons/hicolor/256x256/apps/agenmini.png')
        shutil.copy2(ROOT/'LICENSE',stage/'usr/share/licenses/agenmini/LICENSE')
        py_version=subprocess.check_output([str(python),'--version'],text=True).strip()
        (app/'DEPENDENCIES.json').write_text(json.dumps({'python':py_version,'python_distribution':'astral-sh/python-build-standalone, verified by uv','uv':subprocess.check_output(['uv','--version'],text=True).strip(),'gateway_sha256':hashlib.sha256(gateway.read_bytes()).hexdigest(),'requirements_sha256':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest(),'architecture':machine},indent=2))
        # Invoking modules avoids non-relocatable pip entrypoint shebangs.
        run(python,'-c','import aiohttp,cryptography,lxml,matplotlib,mcp,jwt;print("Private runtime imports OK")')
        run('desktop-file-validate',stage/'usr/share/applications/agenmini.desktop')
        archive_tree(stage,output/f'agenmini-{version}-linux-{arch}.tar.gz')
        control=stage/'DEBIAN';control.mkdir()
        (control/'control').write_text(f'Package: agenmini\nVersion: {version}\nSection: utils\nPriority: optional\nArchitecture: {arch}\nMaintainer: Zwart04 <48742395+Zwart04@users.noreply.github.com>\nDepends: libc6 (>= 2.35), libstdc++6, nodejs, git, xdg-utils\nHomepage: https://zwart04.github.io/agenmini/\nDescription: Agen Mini desktop and CLI with private runtime\n AI workspace; models and provider credentials are configured by the user.\n')
        run('dpkg-deb','--root-owner-group','--build',stage,output/f'agenmini_{version}_{arch}.deb')
        shutil.rmtree(control)
        if arch=='amd64':
            pkginfo=f'pkgname = agenmini\npkgbase = agenmini\npkgver = {version}-1\npkgdesc = Agen Mini desktop and CLI with private Python runtime\nurl = https://zwart04.github.io/agenmini/\nbuilddate = {int(time.time())}\npackager = Zwart04\nsize = {sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())}\narch = x86_64\nlicense = GPL-3.0-or-later\ndepend = glibc>=2.35\ndepend = gcc-libs\ndepend = nodejs\ndepend = git\ndepend = xdg-utils\n'
            tar=work/'arch.tar';archive_tree(stage,tar,pkginfo)
            run('zstd','-T0','-q',tar,'-o',output/f'agenmini-{version}-1-x86_64.pkg.tar.zst')
        rpm=work/'rpm'
        for name in ('BUILD','BUILDROOT','RPMS','SOURCES','SPECS','SRPMS'):(rpm/name).mkdir(parents=True)
        spec=rpm/'SPECS/agenmini.spec'
        spec.write_text(f'''%global debug_package %{{nil}}
%global _build_id_links none
%global __os_install_post %{{nil}}
Name: agenmini
Version: {version}
Release: 1
Summary: Agen Mini desktop and CLI with private Python runtime
License: GPL-3.0-or-later
URL: https://github.com/Zwart04/agenmini
AutoReqProv: no
Requires: glibc >= 2.35, libstdc++, nodejs, git, xdg-utils
%description
AI workspace with a private runtime. Models are not bundled.
%prep
%build
%install
mkdir -p "%{{buildroot}}"
cp -a "{stage}/." "%{{buildroot}}/"
%files
/opt/agenmini
/usr/bin/agenmini
/usr/share/applications/agenmini.desktop
/usr/share/icons/hicolor/256x256/apps/agenmini.png
%license /usr/share/licenses/agenmini/LICENSE
''')
        run('rpmbuild','--define',f'_topdir {rpm}','-bb',spec)
        built=list((rpm/'RPMS').rglob('*.rpm'));assert len(built)==1
        shutil.copy2(built[0],output/built[0].name)
    assets=[p for p in output.iterdir() if p.name.endswith(('.deb','.rpm','.pkg.tar.zst','.tar.gz'))]
    for path in assets:path.with_name(path.name+'.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n')
    print('Native packages ready:',*[p.name for p in assets])


if __name__=='__main__':build()

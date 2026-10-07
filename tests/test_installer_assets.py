"""Installer must preserve binary artwork, including the PNG CRLF signature."""
import io
import tarfile
from pathlib import Path
from build_installer import add

def test_vps_installer_resolves_release_url(tmp_path, monkeypatch):
    import build_installer, re
    root=tmp_path/'source';root.mkdir()
    (root/'app').mkdir();(root/'app/__init__.py').write_text('VERSION = "1.2.3"')
    (root/'installer-head.sh').write_text('# version __VERSI__\n')
    (root/'installer-vps-head.sh').write_text('URL=https://github.com/Zwart04/agenmini/releases/download/v__VERSI__\n')
    monkeypatch.setattr(build_installer,'ROOT',root)
    monkeypatch.setattr(build_installer,'FILES',[])
    build_installer.main()
    source=(root/'dist/pasang-vps.sh').read_text()
    assert '/releases/download/v1.2.3' in source
    assert '__VERSI__' not in source

def test_installer_preserves_provider_logo_bytes():
    source=Path(__file__).resolve().parents[1]/'frontend/providers/openai.png'
    assert source.read_bytes().startswith(b'\x89PNG\r\n')
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w') as tar:add(tar,source,'logo.png')
    archive.seek(0)
    with tarfile.open(fileobj=archive) as tar:
        assert tar.extractfile('logo.png').read()==source.read_bytes()

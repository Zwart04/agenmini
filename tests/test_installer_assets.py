"""Installer must preserve binary artwork, including the PNG CRLF signature."""
import io
import tarfile
from pathlib import Path
from build_installer import add

def test_installer_preserves_provider_logo_bytes():
    source=Path(__file__).resolve().parents[1]/'frontend/providers/openai.png'
    assert source.read_bytes().startswith(b'\x89PNG\r\n')
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w') as tar:add(tar,source,'logo.png')
    archive.seek(0)
    with tarfile.open(fileobj=archive) as tar:
        assert tar.extractfile('logo.png').read()==source.read_bytes()

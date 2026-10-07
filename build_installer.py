"""Bungkus semua berkas jadi satu dist/pasang.sh (skrip + arsip base64 di ujungnya)."""
import base64
import io
import re
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).parent
FILES = ["app", "frontend", "gateway", "docs/DEEPSEEK-CORE.md", "docs/deepseek-harness.LICENSE", "docs/HARNESSES.md", "docs/BRANDING.md", "docs/PROJECT-MAP.md", "docs/SECURITY-AUDIT.md", "UNINSTALL.md", "Dockerfile", "docker-compose.yml", "docker-compose.standalone.yml", ".env.standalone.example", "mcp.example.json", "README.md", "requirements.txt", "requirements.lock", "MODEL-CATALOG.md", "VALIDATION.md", "agen", "agen-standalone", ".dockerignore", "agen-supervisor.sh", "agen-swap.sh", "agen-uninstall.sh", "host-integrations.py", "router-backup.py", "make_vps_backup.py"]
DEFAULT_MODEL = "hf.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M"


def private_path(arc: str) -> bool:
    parts = Path(arc).parts
    name = Path(arc).name.lower()
    return (name.startswith('.env') and name != '.env.standalone.example') or name.endswith(('.pem','.key','.sqlite','.sqlite3','.db')) or any(p in ('data','dist','.git','.local-tools','node_modules') or p.startswith(('.test-tmp','.test-temp','.tmp')) for p in parts)


def add(tar: tarfile.TarFile, path: Path, arc: str):
    if private_path(arc) or path.is_symlink():
        raise ValueError("Private/generated or symlink path cannot be packaged: " + arc)
    if path.is_dir():
        for p in sorted(path.iterdir()):
            if p.name in ("__pycache__",) or p.suffix == ".pyc":
                continue
            add(tar, p, f"{arc}/{p.name}")
        return
    data = path.read_bytes()
    if path.suffix.lower() in {".py", ".js", ".css", ".html", ".sh", ".json", ".yml", ".yaml", ".md", ".txt", ".go", ".mod", ".sum", ".lock", ".example"} or not path.suffix:
        data = data.replace(b"\r\n", b"\n")
    info = tarfile.TarInfo(arc)
    info.size = len(data)
    info.mode = 0o755 if arc in ("agen", "agen-standalone") else 0o644
    info.mtime = int(time.time())
    tar.addfile(info, io.BytesIO(data))


def main():
    version = re.search(r'VERSION = "(.+?)"', (ROOT / "app" / "__init__.py").read_text()).group(1)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in FILES:
            add(tar, ROOT / f, f)
    head = (ROOT / "installer-head.sh").read_text(encoding="utf-8").replace("\r\n", "\n")
    head = head.replace("__VERSI__", version).replace("__MODEL__", DEFAULT_MODEL)
    b64 = base64.encodebytes(buf.getvalue()).decode()
    out = ROOT / "dist" / "pasang.sh"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes((head + b64).encode())
    standalone = (ROOT / "installer-vps-head.sh").read_text(encoding="utf-8").replace("\r\n", "\n")
    standalone = standalone.replace("__VERSI__", version).replace("__MODEL__", DEFAULT_MODEL)
    if "__VERSI__" in standalone or "__MODEL__" in standalone:
        raise ValueError('Unresolved VPS installer release placeholder')
    (ROOT / "dist" / "pasang-vps.sh").write_bytes((standalone + b64).encode())
    print(f"{out}  ({out.stat().st_size / 1024:.0f} KB, versi {version}, model awal {DEFAULT_MODEL})")


if __name__ == "__main__":
    main()

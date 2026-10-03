"""Pengaturan awal dari .env. Nilai yang diubah lewat web disimpan di tabel settings dan menang atas .env."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "db" / "agen.sqlite"
BACKUP_DIR = DATA_DIR / "backup"
WORK_DIR = DATA_DIR / "ruang-kerja"
CERT_DIR = DATA_DIR / "cert"
STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend"

TZ = os.environ.get("TZ", "Asia/Jakarta")

# Nilai awal; bisa ditimpa lewat halaman Pengaturan.
DEFAULTS = {
    "telegram_default_bot": "orchestrator",
    "llm_backend": os.environ.get("LLM_BACKEND", "ollama"),
    "compatible_base": os.environ.get("COMPATIBLE_BASE", "http://host.docker.internal:8080/v1"),
    "compatible_key": os.environ.get("COMPATIBLE_KEY", ""),
    "full_access": "0",
    "tool_mode": os.environ.get("TOOL_MODE", "text"),
    "ollama_url": os.environ.get("OLLAMA_URL", "http://ollama:11434"),
    "model": os.environ.get("MODEL", "hf.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M"),
    "num_ctx": os.environ.get("NUM_CTX", "8192"),
    "keep_alive": os.environ.get("KEEP_ALIVE", "30m"),
    "web_password": os.environ.get("WEB_PASSWORD", ""),
    "telegram_token": os.environ.get("TELEGRAM_TOKEN", ""),
    "telegram_user_ids": os.environ.get("TELEGRAM_USER_IDS", ""),  # dipisah koma, dari @userinfobot
    "online_base": os.environ.get("ONLINE_API_BASE", ""),
    "online_key": os.environ.get("ONLINE_API_KEY", ""),
    "online_model": os.environ.get("ONLINE_MODEL", ""),
    "searx_url": os.environ.get("SEARX_URL", ""),
    "max_steps": "6",
    "max_tokens": "900",  # batas panjang satu jawaban model
    "browser_engine": "auto",  # auto | lightpanda | chromium
    "dns_aman": "1",  # DNS-over-HTTPS untuk permintaan web (lihat net.py)
    "vision_model": os.environ.get("VISION_MODEL", "qwen3.5:0.8b"),  # "mata" untuk membaca gambar
    "image_gen": "1",  # buat gambar lewat Pollinations (internet, gratis); "0" = mati
    "cpu_hemat": "0",  # "1" = sisakan satu inti CPU untuk sistem (jawaban lebih lambat)
}

WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT_INTERNAL", "8443"))
KERJA_UID = int(os.environ.get("KERJA_UID", "1001"))
KERJA_GID = int(os.environ.get("KERJA_GID", "1001"))

#!/bin/bash
# Salin kode terbaru ke ~/agen-uji, bangun ulang image bila perlu, lalu jalankan semua tes di container Linux.
SRC="/mnt/c/Users/Zwart/Downloads/Coding AI/agenmini"
rsync -a --delete --exclude __pycache__ --exclude data --exclude .env "$SRC/" ~/agen-uji/
cd ~/agen-uji
if [ "${1:-}" = "build" ]; then docker compose build 2>&1 | tail -1; fi
docker run --rm -v ~/agen-uji:/src -w /src -e DATA_DIR=/tmp/d --entrypoint sh agenmini:latest -c \
  "pip install -q pytest 2>/dev/null; python -m pytest -q -p no:cacheprovider tests 2>&1 | tail -30"

#!/usr/bin/env bash
# Host supervisor: runtime switching and verified GitHub releases. Never exposes Docker to the app.
set -Eeuo pipefail
DIR=/opt/agenmini
cd "$DIR"
mkdir -p data
[[ -f data/maintenance ]] && exit 0
exec 9>data/supervisor.lock
flock -n 9 || exit 0
touch data/local-runtime.env
compose() { docker compose --env-file .env --env-file data/local-runtime.env -f docker-compose.standalone.yml "$@"; }
RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
AVAILABLE_MB=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
CPUS=$(nproc)
LOCAL_MB=0
LOCAL_ID=$(compose --profile local ps -q local 2>/dev/null || true)
if [[ -n "$LOCAL_ID" ]]; then
  LOCAL_MB=$(docker stats --no-stream --format '{{.MemUsage}}' "$LOCAL_ID" 2>/dev/null | awk '{n=$1; if(n~/GiB/) n=n*1024; else if(n~/KiB/) n=n/1024; print int(n)}' || echo 0)
fi
[[ "$LOCAL_MB" =~ ^[0-9]+$ ]] || LOCAL_MB=0
jq -n --argjson ram_mb "$RAM_MB" --argjson available_mb "$AVAILABLE_MB" --argjson cpus "$CPUS" --argjson local_memory_mb "$LOCAL_MB" --arg architecture "$(uname -m)" '{ram_mb:$ram_mb,available_mb:$available_mb,cpus:$cpus,local_memory_mb:$local_memory_mb,architecture:$architecture}' > data/hardware.json.tmp
mv data/hardware.json.tmp data/hardware.json
write_status() {
  local file="$1" message="$2"
  jq -n --arg message "$message" --arg time "$(date -Is)" '{message:$message,checked_at:$time}' > "data/$file.tmp"
  mv "data/$file.tmp" "data/$file"
}
if [[ -f data/runtime-request && ( -f data/model-busy || -f data/task-busy ) ]]; then exit 0; fi
if [[ -f data/runtime-request ]]; then
  MODE=$(cat data/runtime-request)
  mv data/runtime-request data/runtime-processing
  if [[ "$MODE" == local ]]; then
    write_status runtime-status.json 'Menyiapkan model lokal; unduhan pertama dapat memerlukan beberapa menit.'
    if [[ -f data/local-model-request ]]; then
      MODEL_ID=$(cat data/local-model-request)
      if MODEL_JSON=$(compose exec -T agen python -m app.local_models "$MODEL_ID"); then
        MIN_RAM=$(echo "$MODEL_JSON" | jq -r '.min_ram_gb * 1024')
        NEED_MB=$(echo "$MODEL_JSON" | jq -r '.runtime_mb')
        if (( RAM_MB < MIN_RAM )); then
          write_status runtime-status.json 'RAM host tidak cukup untuk model ini.'
          rm -f data/local-model-request data/runtime-processing
          exit 0
        fi
        compose --profile local stop local || true
        AVAILABLE_MB=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
        if (( AVAILABLE_MB < NEED_MB + 700 )); then
          write_status runtime-status.json 'RAM tersedia belum cukup; tutup layanan lain. Model sebelumnya dipulihkan bila ada.'
          compose --profile local up -d local || true
          rm -f data/local-model-request data/runtime-processing
          exit 0
        fi
        REPO=$(echo "$MODEL_JSON" | jq -r '.repo')
        FILE=$(echo "$MODEL_JSON" | jq -r '.file')
        THREADS=$((CPUS>1 ? CPUS-1 : 1)); (( THREADS>4 )) && THREADS=4
        printf 'LOCAL_REPO=%s\nLOCAL_FILE=%s\nLOCAL_MEM_LIMIT=%sm\nLOCAL_THREADS=%s\n' "$REPO" "$FILE" "$NEED_MB" "$THREADS" > data/local-runtime.env.tmp
        mv data/local-runtime.env.tmp data/local-runtime.env
        rm -f data/local-model-request
      else
        write_status runtime-status.json 'Model tidak dikenal; pilihan dibatalkan.'
        rm -f data/local-model-request data/runtime-processing
        exit 0
      fi
    fi
    if compose --profile local up -d local; then
      compose --profile router stop router
      write_status runtime-status.json 'Model lokal dinyalakan. Chat siap setelah model selesai dimuat; lihat agen lokal-log.'
    else
      write_status runtime-status.json 'Model lokal gagal dinyalakan. Periksa agen lokal-log dan RAM VPS.'
    fi
  elif [[ "$MODE" == api ]]; then
    compose --profile local stop local
    compose --profile router up -d router
    write_status runtime-status.json 'Mode API aktif; mesin model lokal dihentikan untuk menghemat RAM.'
  fi
  rm -f data/runtime-processing
fi
ACTION=""
if [[ -f data/update-request ]]; then
  ACTION=$(cat data/update-request)
  rm -f data/update-request
elif [[ -f data/auto-update.enabled ]]; then
  LAST=$(cat data/update-last-check 2>/dev/null || echo 0)
  [[ "$LAST" =~ ^[0-9]+$ ]] || LAST=0
  if (( $(date +%s) - LAST >= 86400 )); then ACTION=install; fi
fi
[[ -n "$ACTION" ]] || exit 0
if [[ -f data/model-busy || -f data/task-busy ]]; then
  printf '%s' "$ACTION" > data/update-request
  exit 0
fi
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
API=https://api.github.com/repos/Zwart04/agenmini/releases/latest
if ! curl -fsSL --retry 2 --max-time 30 "$API" -o "$TMP/release.json"; then
  write_status update-status.json 'Tidak bisa memeriksa GitHub; update belum dipasang.'
  exit 0
fi
date +%s > data/update-last-check
TAG=$(jq -r '.tag_name // empty' "$TMP/release.json")
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { write_status update-status.json 'Tag release stabil tidak valid.'; exit 1; }
CURRENT=$(sed -n 's/^VERSION = "\([^"]*\)"/\1/p' app/__init__.py | tr -d '\r')
if [[ "$TAG" == "v$CURRENT" ]]; then write_status update-status.json "Versi $CURRENT sudah terbaru."; exit 0; fi
if [[ "$(printf '%s\n' "$CURRENT" "${TAG#v}" | sort -V | tail -1)" == "$CURRENT" ]]; then
  write_status update-status.json "Versi $CURRENT lebih baru dari release GitHub; tidak melakukan downgrade."
  exit 0
fi
write_status update-status.json "Release $TAG tersedia."
[[ "$ACTION" == install ]] || exit 0
URL=$(jq -r '.assets[] | select(.name=="pasang-vps.sh") | .browser_download_url' "$TMP/release.json")
HASH_URL=$(jq -r '.assets[] | select(.name=="pasang-vps.sha256") | .browser_download_url' "$TMP/release.json")
for url in "$URL" "$HASH_URL"; do
  [[ "$url" == "https://github.com/Zwart04/agenmini/releases/download/$TAG/"* ]] || { write_status update-status.json 'Alamat aset release tidak valid.'; exit 1; }
done
curl -fsSL --retry 2 --max-time 180 "$URL" -o "$TMP/pasang-vps.sh"
curl -fsSL --retry 2 --max-time 30 "$HASH_URL" -o "$TMP/pasang-vps.sha256"
EXPECTED=$(awk 'NR==1 {print $1}' "$TMP/pasang-vps.sha256")
[[ "$EXPECTED" =~ ^[a-f0-9]{64}$ ]] || exit 1
[[ "$(sha256sum "$TMP/pasang-vps.sh" | cut -d' ' -f1)" == "$EXPECTED" ]] || { write_status update-status.json 'Checksum release tidak cocok; pemasangan dibatalkan.'; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="data/backup/update-$STAMP"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
compose exec -T agen python -c 'from app import scheduler; scheduler.backup_db()'
tar --exclude='./data' --exclude='./.git' --exclude='./.reference' --exclude='./dist' -czf "$BACKUP/code.tar.gz" .
write_status update-status.json "Memasang $TAG; backup dibuat di $BACKUP."
if AGEN_OTOMATIS=1 bash "$TMP/pasang-vps.sh" > "$BACKUP/install.log" 2>&1; then
  write_status update-status.json "Update $TAG berhasil."
else
  tar -xzf "$BACKUP/code.tar.gz" -C "$DIR"
  compose --profile router up -d --build || true
  write_status update-status.json "Update gagal. Kode sebelumnya dipulihkan; lihat $BACKUP/install.log."
  exit 1
fi

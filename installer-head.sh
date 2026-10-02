#!/usr/bin/env bash
# ============================================================================
#  Pemasang Agen Mini  —  versi __VERSI__
#  Jalankan sebagai root:   bash pasang.sh
#  Menjalankan ulang berkas versi baru = memperbarui (data & pengaturan aman).
# ============================================================================
set -euo pipefail
DIR=/opt/agenmini
DEFAULT_MODEL="__MODEL__"

h() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }
ok() { printf '  \033[32mok\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31mGAGAL: %s\033[0m\n' "$*"; exit 1; }
# AGEN_OTOMATIS=1 bash pasang.sh  → semua pertanyaan memakai jawaban saran (tanpa tanya jawab)
ask() {
  local q="$1" def="${2:-}" a=""
  if [ "${AGEN_OTOMATIS:-0}" = 1 ]; then echo "$def"; return; fi
  read -r -p "  $q${def:+ [$def]}: " a </dev/tty || true
  echo "${a:-$def}"
}
yes_no() { local a; a=$(ask "$1 (y/n)" "${2:-y}"); [[ "$a" =~ ^[YyJj] ]]; }

[ "$(id -u)" = 0 ] || die "Jalankan sebagai root (sudo bash $0)."
command -v docker >/dev/null || die "Docker tidak ditemukan. (1Panel biasanya sudah memasangnya.)"
docker compose version >/dev/null 2>&1 || die "Plugin 'docker compose' tidak ada."

h "1/6 Menyiapkan berkas"
UPDATE=0; [ -f "$DIR/.env" ] && UPDATE=1
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
sed -n '/^__ARSIP_DI_BAWAH__$/,$p' "$0" | tail -n +2 | base64 -d | tar -xz -C "$TMP"
mkdir -p "$DIR/data"
rm -rf "$DIR/app"
cp -r "$TMP"/. "$DIR"/
install -m 755 "$DIR/agen" /usr/local/bin/agen
ok "berkas ada di $DIR  ($([ $UPDATE = 1 ] && echo 'mode PERBARUI' || echo 'pemasangan baru'))"

env_get() { { grep -E "^$1=" "$DIR/.env" 2>/dev/null || true; } | head -1 | cut -d= -f2-; }

h "2/6 Mencari Ollama"
OC=$(docker ps --format '{{.Names}} {{.Image}}' | awk 'tolower($0) ~ /ollama/ {print $1; exit}')
[ -n "$OC" ] || die "Container Ollama tidak ditemukan. Pasang/nyalakan Ollama dari App Store 1Panel dulu."
NET=$(docker inspect "$OC" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')
if [ -z "$NET" ] || [ "$NET" = "bridge" ] || [ "$NET" = "host" ]; then
  docker network inspect agen-ollama >/dev/null 2>&1 || docker network create agen-ollama >/dev/null
  docker network connect agen-ollama "$OC" 2>/dev/null || true
  NET=agen-ollama
fi
OLLAMA_URL="http://$OC:11434"
OVER=$(docker exec "$OC" ollama --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
ok "Ollama: $OC (versi ${OVER:-?}), jaringan: $NET"
MODELS=$(docker exec "$OC" ollama list 2>/dev/null | awk 'NR>1{print $1}' || true)

if [ $UPDATE = 0 ]; then
  h "3/6 Beberapa pertanyaan (Enter = pakai saran)"
  PORT=443; if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '[:.]443$'; then PORT=8443; fi
  PORT=$(ask "Port web" "$PORT")
  PW=$(ask "Kata sandi web (kosong = dibuatkan)" "")
  [ -n "$PW" ] || PW=$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | cut -c1-12)
  TG=$(ask "Token bot Telegram dari @BotFather (boleh kosong, bisa diisi nanti)" "")
  TGID=""
  if [ -n "$TG" ]; then
    echo "  User ID Telegram Anda: buka @userinfobot di Telegram, kirim /start, salin angka Id."
    TGID=$(ask "User ID Telegram yang diizinkan (pisahkan koma bila lebih dari satu)" "")
  fi
  echo "  Model yang sudah ada di Ollama:"; echo "$MODELS" | sed 's/^/    • /'
  MODEL=$(ask "Model awal" "$DEFAULT_MODEL")
  CHROMIUM=1; yes_no "Pasang Chromium sebagai browser cadangan? (+±450 MB disk)" y || CHROMIUM=0
  IP=$(curl -s -m 6 https://api.ipify.org || true)
  [[ "$IP" =~ ^[0-9.]+$ ]] || IP=$(hostname -I | awk '{print $1}')
  IP=$(ask "IP publik VPS" "$IP")
  umask 077
  cat > "$DIR/.env" <<EOF
OLLAMA_URL=$OLLAMA_URL
OLLAMA_NETWORK=$NET
WEB_PORT=$PORT
WEB_PASSWORD=$PW
MODEL=$MODEL
TELEGRAM_TOKEN=$TG
TELEGRAM_USER_IDS=$TGID
PUBLIC_IP=$IP
CHROMIUM=$CHROMIUM
TZ=Asia/Jakarta
EOF
  chmod 600 "$DIR/.env"
else
  h "3/6 Memakai pengaturan lama"
  sed -i "s|^OLLAMA_URL=.*|OLLAMA_URL=$OLLAMA_URL|; s|^OLLAMA_NETWORK=.*|OLLAMA_NETWORK=$NET|" "$DIR/.env"
  PORT=$(env_get WEB_PORT); IP=$(env_get PUBLIC_IP); MODEL=$(env_get MODEL); PW=""
  ok "port $PORT, IP $IP"
fi

h "4/6 Swap (cadangan RAM)"
if [ -z "$(swapon --show --noheadings 2>/dev/null)" ]; then
  if yes_no "Belum ada swap. Buat swap 2 GB supaya tidak mati saat RAM penuh?" y; then
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -q -w vm.swappiness=10; echo 'vm.swappiness=10' > /etc/sysctl.d/99-agenmini.conf
    ok "swap 2 GB aktif"
  fi
else
  ok "swap sudah ada"
fi

h "5/6 Membangun & menyalakan (pertama kali ±3-8 menit)"
cd "$DIR"
docker compose build --build-arg CHROMIUM="$(env_get CHROMIUM)" 2>&1 | grep -E '^#[0-9]+ \[|ERROR|error' | sed 's/^/  /' || true
docker image inspect agenmini:latest >/dev/null 2>&1 || die "Gagal membangun image. Jalankan: cd $DIR && docker compose build"
docker compose up -d --force-recreate 2>&1 | sed 's/^/  /'
SCHEME=https
for i in $(seq 1 45); do
  if curl -fsk "https://127.0.0.1:$PORT/sehat" >/dev/null 2>&1; then break; fi
  sleep 2
  [ "$i" = 45 ] && { docker logs --tail 30 agenmini; die "Agen tidak menyala. Lihat log di atas."; }
done
ok "agen menyala"
# kata sandi sudah disimpan (ter-hash) di database; hapus dari .env
sed -i '/^WEB_PASSWORD=/d' "$DIR/.env"

if ! echo "$MODELS" | grep -qxF "$MODEL" && ! echo "$MODELS" | grep -qxF "$MODEL:latest"; then
  h "Mengunduh model $MODEL"
  docker exec -i agenmini python -m app.cli pull "$MODEL" || warn "Gagal mengunduh model. Coba: agen unduh $MODEL"
fi
# "mata" agen untuk membaca gambar yang dikirim pengguna
VM=$(docker exec agenmini python -c "from app import db; print(db.setting('vision_model'))" 2>/dev/null || echo "qwen3.5:0.8b")
if [ -n "$VM" ] && ! echo "$MODELS" | grep -qxF "$VM" && ! echo "$MODELS" | grep -qxF "$VM:latest"; then
  h "Mengunduh model penglihatan $VM (untuk membaca gambar, ±1 GB)"
  docker exec -i agenmini python -m app.cli pull "$VM" || warn "Gagal mengunduh. Coba: agen unduh $VM"
fi

h "6/6 Firewall"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow "$PORT"/tcp >/dev/null && ok "ufw: port $PORT dibuka"
elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
  firewall-cmd -q --permanent --add-port="$PORT"/tcp && firewall-cmd -q --reload && ok "firewalld: port $PORT dibuka"
else
  ok "firewall lokal tidak aktif"
fi
warn "Buka juga port TCP $PORT di panel penyedia VPS (Tencent Cloud: Security Group / Firewall instance)."

CODE=$(docker exec agenmini python -c "from app import db; print(db.setting('pair_code'))" 2>/dev/null || echo "?")
URL="https://$IP$( [ "$PORT" = 443 ] || echo ":$PORT")"
printf '\n\033[1;32m════════════════════════════════════════════════════════════\033[0m\n'
printf '  \033[1mAgen Mini siap!\033[0m\n\n'
printf '  Web        : \033[1m%s\033[0m\n' "$URL"
[ -n "$PW" ] && printf '  Kata sandi : \033[1m%s\033[0m   (catat! bisa diganti di Pengaturan)\n' "$PW"
if [ -n "$(env_get TELEGRAM_USER_IDS)" ]; then printf '  Telegram   : User ID %s diizinkan. Buka bot Anda, kirim /start\n' "$(env_get TELEGRAM_USER_IDS)"
else printf '  Telegram   : kirim  \033[1m/kode %s\033[0m  ke bot Anda (atau: agen izinkan <user id>)\n' "$CODE"; fi
printf '  Model      : %s\n\n' "$MODEL"
printf '  Browser akan memperingatkan "tidak aman" karena sertifikatnya buatan sendiri\n'
printf '  Klik Lanjutan, lalu Lanjutkan. Koneksi tetap terenkripsi.\n\n'
printf '  Perintah: agen status, agen log, agen uji, agen bantuan\n'
printf '\033[1;32m════════════════════════════════════════════════════════════\033[0m\n'
exit 0
__ARSIP_DI_BAWAH__

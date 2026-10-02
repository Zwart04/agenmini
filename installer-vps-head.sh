#!/usr/bin/env bash
# Pemasang mandiri untuk VPS Ubuntu/Debian kosong, tanpa Ollama.
set -Eeuo pipefail
DIR=/opt/agenmini
trap 'echo "Pemasangan berhenti pada baris $LINENO. Periksa pesan galat di atas, lalu jalankan pemasang lagi." >&2' ERR
fail() { echo "GAGAL: $*" >&2; exit 1; }
step() { printf '\n== %s ==\n' "$*"; }
ask() {
  local value=""
  if [[ "${AGEN_OTOMATIS:-0}" != 1 && -t 0 ]]; then
    read -r -p "$1 [$2]: " value || true
  fi
  printf '%s' "${value:-$2}"
}
[[ $(id -u) == 0 ]] || fail "Gunakan sudo bash $0 atau login sebagai root."
[[ -r /etc/os-release ]] || fail "Tidak bisa mengenali OS."
. /etc/os-release
case "$ID" in
  ubuntu|debian) ;;
  *) fail "Pemasang ini mendukung Ubuntu/Debian. Pilih Ubuntu 24.04 untuk VPS baru." ;;
esac
case "$(uname -m)" in
  x86_64|aarch64) ;;
  *) fail "Membutuhkan CPU amd64 atau arm64." ;;
esac
if [[ "${AGEN_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  echo "Pemeriksaan OS/arsitektur berhasil: $ID $(uname -m)"
  exit 0
fi
step "1/5 Menyiapkan paket dan Docker"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl openssl tar coreutils iproute2 jq util-linux
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL --retry 3 "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/agenmini-docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
elif ! docker compose version >/dev/null 2>&1; then
  apt-get install -y docker-compose-plugin
fi
if command -v systemctl >/dev/null; then systemctl enable --now docker; fi
docker info >/dev/null || fail "Docker belum berjalan. Jalankan systemctl start docker."
docker compose version >/dev/null || fail "Docker Compose belum tersedia."
step "2/5 Menyalin aplikasi"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
sed -n '/^__ARSIP_DI_BAWAH__$/,$p' "$0" | tail -n +2 | base64 -d | tar -xz -C "$TMP"
mkdir -p "$DIR/data"
cp -a "$TMP"/. "$DIR"/
install -m 755 "$DIR/agen-standalone" /usr/local/bin/agen
step "3/5 Pengaturan awal"
if [[ ! -f "$DIR/.env" ]]; then
  PORT=443
  if ss -ltnH | awk '{print $4}' | grep -qE '[:.]443$'; then PORT=8443; fi
  PORT=$(ask "Port web" "$PORT")
  [[ "$PORT" =~ ^[0-9]+$ && "$PORT" -ge 1 && "$PORT" -le 65535 ]] || fail "Port tidak valid."
  IP=$(curl -4fsS --max-time 8 https://api.ipify.org || true)
  IP=$(ask "IPv4 publik VPS" "${IP:-127.0.0.1}")
  [[ "$IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail "Masukkan IPv4 publik VPS."
  PW=$(openssl rand -hex 12)
  umask 077
  cat > "$DIR/.env" <<EOF
WEB_PASSWORD=$PW
WEB_PORT=$PORT
PUBLIC_IP=$IP
TZ=Asia/Jakarta
LLM_BACKEND=compatible
COMPATIBLE_BASE=http://router:20128/v1
COMPATIBLE_KEY=
MODEL=pilih-model-di-9router
TOOL_MODE=text
NUM_CTX=4096
CHROMIUM=0
AGEN_MEM_LIMIT=800m
ROUTER_MEM_LIMIT=768m
NINE_ROUTER_IMAGE=decolua/9router@sha256:4316fefb95ea642d57db885d906b1227b1768b15ac5def314621fd781da7b3f1
EOF
  chmod 600 "$DIR/.env"
else
  echo "Pengaturan dan data lama dipertahankan."
fi
get_env() { sed -n "s/^$1=//p" "$DIR/.env" | head -1; }
[[ $(get_env LLM_BACKEND) =~ ^(compatible|router|local)$ ]] || fail "Instalasi lama memakai backend lain. Ganti backend lewat web dahulu; pemasang ini khusus mode tanpa Ollama."
if ! grep -q '^ROUTER_JWT_SECRET=.' "$DIR/.env"; then
  printf '\nROUTER_JWT_SECRET=%s\n' "$(openssl rand -hex 32)" >> "$DIR/.env"
fi
sed -i 's|^NINE_ROUTER_IMAGE=decolua/9router:latest$|NINE_ROUTER_IMAGE=decolua/9router@sha256:4316fefb95ea642d57db885d906b1227b1768b15ac5def314621fd781da7b3f1|' "$DIR/.env"
chmod 600 "$DIR/.env"
step "4/5 Membangun dan menyalakan"
cd "$DIR"
rm -f data/maintenance
docker compose -f docker-compose.standalone.yml --profile router config --quiet
docker compose -f docker-compose.standalone.yml --profile router up -d --build
ACTIVE_MODE=$(docker compose -f docker-compose.standalone.yml exec -T agen python -c 'from app import db; print(db.setting("llm_backend"))' 2>/dev/null || true)
if [[ "$ACTIVE_MODE" == local ]]; then echo local > data/runtime-request; fi
if command -v systemctl >/dev/null; then
  cat > /etc/systemd/system/agenmini-supervisor.service <<EOF
[Unit]
Description=Agen Mini runtime and release supervisor
After=docker.service network-online.target
[Service]
Type=oneshot
TimeoutStartSec=1800
ExecStart=/bin/bash /opt/agenmini/agen-supervisor.sh
EOF
  cat > /etc/systemd/system/agenmini-supervisor.timer <<EOF
[Unit]
Description=Check Agen Mini runtime requests
[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now agenmini-supervisor.timer
fi
step "5/5 Menunggu aplikasi siap"
PORT=$(get_env WEB_PORT)
READY=0
for _ in $(seq 1 90); do
  if curl -fkSs --max-time 3 "https://127.0.0.1:$PORT/sehat" >/dev/null 2>&1; then READY=1; break; fi
  sleep 2
done
[[ $READY == 1 ]] || { docker compose -f docker-compose.standalone.yml --profile router logs --tail 60; fail "Agen belum sehat. Periksa log di atas."; }
ROUTER_READY=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://127.0.0.1:20128/api/health >/dev/null 2>&1; then ROUTER_READY=1; break; fi
  sleep 2
done
[[ $ROUTER_READY == 1 ]] || fail "9router belum sehat. Lihat agen router-log."
IP=$(get_env PUBLIC_IP)
SUFFIX=""; [[ "$PORT" == 443 ]] || SUFFIX=":$PORT"
printf '\nTERPASANG\nWeb Agen Mini: https://%s%s\n' "$IP" "$SUFFIX"
if [[ -n "${PW:-}" ]]; then printf 'Kata sandi web: %s\n' "$PW"; else echo "Gunakan kata sandi lama; reset dengan: agen sandi"; fi
printf '\nBuka port TCP %s di firewall panel VPS.\n' "$PORT"
echo "Buka menu AI & 9router di web: API key penghubung dibuat otomatis."
echo "Login provider atau masukkan API key provider langsung di menu tersebut, lalu pilih model."
echo "Mode lokal tanpa Ollama juga tersedia di menu yang sama; unduhan model dilakukan saat dipilih."
echo "MCP: Koneksi MCP | prosedur: Skill | karakter bot: Workspace | update: Versi & Update"
echo "Lokasi: /opt/agenmini | status: agen status | log: agen log"
exit 0
__ARSIP_DI_BAWAH__

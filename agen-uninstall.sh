#!/usr/bin/env bash
# Remove only this installation. Shared Docker, host accounts and other apps remain.
set -euo pipefail
DIR=/opt/agenmini
all=0; yes=0; dry=0
for arg in "$@"; do
  case "$arg" in --all) all=1;; --yes) yes=1;; --dry-run) dry=1;; *) echo 'Usage: agen uninstall [--all --yes] [--dry-run]'; exit 2;; esac
done
if (( dry )); then
  echo "Stop agenmini-supervisor.timer/service; remove Compose project agenmini containers/network and its local images."
  if (( all )); then echo "Delete Agen Mini volumes, $DIR, /usr/local/bin/agen and supervisor units."; else echo "Keep data, .env and provider volumes in $DIR."; fi
  exit 0
fi
[[ $EUID == 0 ]] || { echo 'Jalankan dengan sudo.'; exit 1; }
if (( !yes )); then
  echo 'Agen Mini akan dihentikan dan dihapus.'
  (( !all )) || echo 'SELURUH data, sandi, riwayat, konfigurasi dan model Agen Mini ikut dihapus.'
  read -r -p 'Ketik HAPUS untuk melanjutkan: ' answer
  [[ "$answer" == HAPUS ]] || exit 1
fi
# Disable recovery before stopping the app, including a timer invocation in progress.
systemctl disable --now agenmini-supervisor.timer agenmini-supervisor.service 2>/dev/null || true
if [[ -d "$DIR" ]]; then
  cd "$DIR"
  files=(); [[ ! -f .env ]] || files+=(--env-file .env)
  [[ ! -f data/local-runtime.env ]] || files+=(--env-file data/local-runtime.env)
  compose=docker-compose.standalone.yml; [[ -f "$compose" ]] || compose=docker-compose.yml
  if [[ -f "$compose" ]]; then
    flags=(--remove-orphans --rmi local); (( !all )) || flags+=(--volumes)
    docker compose --project-name agenmini "${files[@]}" -f "$compose" --profile '*' down "${flags[@]}"
  else echo 'Compose tidak ditemukan; penghapusan dibatalkan agar tidak meninggalkan layanan aktif.'; exit 1; fi
fi
rm -f /etc/systemd/system/agenmini-supervisor.service /etc/systemd/system/agenmini-supervisor.timer
systemctl daemon-reload
rm -f /usr/local/bin/agen
if (( all )); then cd /; rm -rf -- "$DIR"; echo 'Agen Mini dan seluruh datanya sudah dihapus.'; else echo "Layanan dihapus; data tersimpan di $DIR. Gunakan pemasang untuk memasang kembali."; fi

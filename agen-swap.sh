#!/usr/bin/env bash
# Only opt-in host swap. Never resize/remove a user's existing swap.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'Swap memerlukan root.' >&2; exit 1; }
GB=${1:-0}
[[ "$GB" =~ ^(0|2|4|8)$ ]] || { echo 'Pilih swap 0, 2, 4 atau 8 GB.' >&2; exit 1; }
[[ "$GB" == 0 ]] && { echo 'Swap tidak diubah.'; exit 0; }
if [[ -n $(swapon --show --noheadings --output NAME) ]]; then echo 'Swap sudah tersedia; dipertahankan tanpa diubah.'; exit 0; fi
SWAP_DIR=/var/lib/agenmini
FSTAB=/etc/fstab
if [[ ${AGEN_INSTALLER_TEST_CONTAINER:-0} == 1 && -f /.dockerenv ]]; then SWAP_DIR=/tmp/agenmini-swap-test; FSTAB=/tmp/agenmini-fstab-test; fi
[[ ! -L "$SWAP_DIR" ]] || { echo 'Direktori swap tidak aman.' >&2; exit 1; }
mkdir -p "$SWAP_DIR";chmod 700 "$SWAP_DIR"
FILE="$SWAP_DIR/swapfile"
[[ ! -e "$FILE" && ! -L "$FILE" && ! -e "$FILE.pending" ]] || { echo 'Berkas swap sudah ada; tidak ditimpa.' >&2; exit 1; }
FREE=$(df -Pk "$SWAP_DIR" | awk 'NR==2 {print $4}')
(( FREE > (GB+1)*1024*1024 )) || { echo 'Disk tidak cukup: sisakan 1 GB selain ukuran swap.' >&2; exit 1; }
cleanup() { rm -f -- "$FILE.pending"; }
trap cleanup EXIT
umask 077
fallocate -l "${GB}G" "$FILE.pending"
chmod 600 "$FILE.pending"
mkswap "$FILE.pending" >/dev/null
mv "$FILE.pending" "$FILE"
if ! swapon "$FILE"; then rm -f -- "$FILE"; echo 'Swap gagal diaktifkan; fstab tidak diubah.' >&2; exit 1; fi
if ! printf '%s none swap sw 0 0\n' "$FILE" >> "$FSTAB"; then
  swapoff "$FILE";rm -f -- "$FILE";echo 'Tidak bisa menyimpan swap ke fstab.' >&2;exit 1
fi
echo "Swap $GB GB aktif. Ini ruang cadangan disk, bukan tambahan RAM fisik."

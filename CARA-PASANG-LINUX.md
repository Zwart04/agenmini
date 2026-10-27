# Agen Mini di Linux — aplikasi dan CLI

Paket native menyediakan menu aplikasi **Agen Mini** dan perintah `agenmini`.
Python privat dan gateway Go ikut dalam paket. Antarmuka memakai browser lokal,
tanpa Electron, Docker, unduhan model, atau layanan root. Node.js, Git dan
xdg-utils dipasang sebagai dependensi distro; harness eksternal tetap opsional.

Unduh dari [website](https://zwart04.github.io/agenmini/) atau
[rilis resmi](https://github.com/Zwart04/agenmini/releases/latest).
Pilih amd64/x86_64 untuk Intel/AMD, arm64/aarch64 untuk ARM.
Verifikasi berkas dengan checksum pendamping sebelum memasang:

```sh
sha256sum -c NAMA-PAKET.sha256
```

## Debian / Ubuntu / Mint

```sh
sudo apt install ./agenmini_0.11.0_amd64.deb
```

Untuk ARM64 pilih berkas `_arm64.deb`.

## Fedora

```sh
sudo dnf install ./agenmini-0.11.0-1.x86_64.rpm
```

Untuk ARM64 pilih berkas `.aarch64.rpm`. Paket RPM ini bukan repositori Fedora
resmi. Distribusi RPM lain harus memenuhi dependensinya sendiri.

## Arch / EndeavourOS / Manjaro

```sh
sudo pacman -U ./agenmini-0.11.0-1-x86_64.pkg.tar.zst
```

Unduhan langsung untuk x86_64; bukan paket AUR atau repositori bertanda tangan.

## Portable GNU/Linux

Arsip `.tar.gz` untuk glibc 2.35+, x86_64/ARM64. Alpine/musl, Android dan
NixOS tidak dinyatakan didukung. Pasang Node.js, Git, xdg-utils melalui distro,
lalu ekstrak tanpa sudo dan jalankan Python privat melalui path hasil ekstraksi:

```sh
tar -xzf agenmini-0.11.0-linux-amd64.tar.gz
./opt/agenmini/runtime/bin/python3 ./opt/agenmini/launcher.py open
```

Wrapper `usr/bin/agenmini` di arsip ditujukan untuk paket `/opt`; untuk portable
gunakan perintah Python di atas. Tidak perlu menyalin ke direktori sistem.

## Mulai, sandi, model dan provider

```sh
agenmini open
agenmini start --no-browser
agenmini status
agenmini password
agenmini provider online
agenmini model ID-MODEL-ANDA
agenmini coffee
agenmini license
agenmini stop
```

Jalankan aplikasi sebagai pengguna biasa. Setup pertama membuka halaman lokal
privat dengan sandi awal; salin sebelum membuka login aplikasi. `password`
menampilkan sandi awal, sedangkan `password SANDI-BARU` mengganti sandi akun.
Halaman sandi hanya berkas privat, tidak dilayani sebagai endpoint HTTP.

Di aplikasi buka **Pengaturan → Koneksi AI & model** untuk endpoint, API key,
gateway OAuth, dan model aktif. Anda dapat menggantinya tanpa memasang ulang.
Model juga dapat dipilih per chat/bot. Gateway bawaan memakai loopback dan
secret acak privat. Tidak ada akun atau API key publik yang ditanam di paket.

Untuk llama.cpp/Ollama yang sudah berjalan, gunakan **API langsung**, endpoint
OpenAI-compatible `/v1` dan ID model yang benar. Jika server memerlukan key,
isi key server tersebut. Pengunduhan model otomatis memerlukan instalasi VPS
dengan supervisor, bukan paket desktop. Harness npm eksternal memerlukan npm;
seluruh runtime tidak dipasang sekaligus.

## Data, update dan remove

Data berada di `~/.local/share/agenmini`, atau `$AGENMINI_DATA_DIR` jika diatur.
Folder privat berizin 0700; sandi/secret berizin 0600. Log ada di `desktop.log`.
Server web hanya mendengarkan `127.0.0.1:8765`, gateway pada `127.0.0.1:20128`.
Port dapat diubah melalui `AGENMINI_PORT` dan `AGENMINI_GATEWAY_PORT`.

Desktop berjalan dengan hak pengguna Anda. Mode akses penuh dapat menjalankan
alat dengan hak tersebut; ini bukan isolasi container. Gunakan izin bawaan
dan tinjau tindakan sebelum memberi akses penuh.

Selesaikan tugas, buat backup dari Pengaturan, lalu jalankan `agenmini stop`
sebelum memasang versi paket baru dengan perintah package manager yang sama.
Jangan hapus data. Pengaturan → Update menyediakan tautan paket rilis terbaru;
desktop tidak menjalankan updater root atau perintah shell dari model AI.

```sh
agenmini stop
sudo apt remove agenmini       # Debian/Ubuntu
sudo dnf remove agenmini       # Fedora, pilih salah satu
sudo pacman -R agenmini        # Arch, pilih salah satu
```

Paket tidak menghapus folder data pengguna. Untuk portable, hentikan memakai
launcher yang sama lalu hapus hanya folder ekstraksi yang Anda buat.

## Lisensi

Karya asli Agen Mini mulai 0.11.0: GPL-3.0-or-later, copyright (C) 2026 Zwart04,
tanpa jaminan. Source tersedia pada rilis yang sama. Lihat `LICENSE` dan
`THIRD_PARTY_NOTICES.md`; komponen pihak ketiga mempertahankan lisensinya.

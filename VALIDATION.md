# Validasi Agen Mini 0.5.5

Pemeriksaan ini membedakan regresi kode, integrasi layanan dan kualitas keluaran model.

## Pemeriksaan

- Regresi Linux: 212 tes pada runtime Python aplikasi, memakai database terpisah. Cakupan meliputi autentikasi, alat, argumen terstruktur, checkpoint, izin, CRUD, arsip proyek dan preservasi berkas.
- Chromium nyata: empat menu di viewport 1440, 1280, 320, 390 dan 430 piksel. Pemeriksaan overflow horizontal, JavaScript, bagian fitur yang terlihat, scroll, dialog rincian dan pagination. Pemeriksaan dilakukan pada antarmuka kandidat serta pemasangan setelah update.
- Pilihan provider/model, draft formulir dan log tidak ditimpa polling. Kantor memakai status server/SSE; diskusi tidak membuat progres tugas palsu.
- ZIP source/pemasangan: CRC, SHA256, versi dan daftar berkas diperiksa. Source berasal dari berkas Git terlacak, tanpa data instalasi, database, log privat, kredensial atau bobot model.
- Pipeline release mensyaratkan CI Linux dan pemasangan/update/uninstall Windows pada commit yang sama. Aset publik kemudian diunduh ulang dan checksum diverifikasi.
- Pemasang/supervisor diuji dalam lingkungan sekali pakai untuk preservasi konfigurasi/data, pergantian skrip atomik, penundaan saat sibuk dan penolakan checksum tidak valid. Perintah paket/Docker pada tes pemasang tertentu menggunakan mock.

## Batas

Browser dan regresi tidak membuktikan semua proyek kompleks dapat selesai. Mutu HTML, game, aplikasi dan riset bergantung model serta spesifikasi tugas. Model kecil tetap berpotensi salah; skill dan pemeriksaan alat bukan jaminan bebas halusinasi.

Pengujian tidak melakukan email, posting sosial, perubahan iklan, pembayaran atau trading. Integrasi layanan tersebut memerlukan kredensial, izin dan pemeriksaan tersendiri. Koneksi yang terkonfigurasi belum membuktikan semua model memiliki kuota.

Tes pemasang sekali pakai bukan bukti instalasi pada semua penyedia VPS kosong. GPU, semua varian GGUF, OAuth seluruh provider, serta pemulihan bencana pada setiap sistem tidak diuji. Windows native memakai API; layanan lokal yang dikelola memerlukan Linux/WSL/Docker.

Bukti operasional dan log akun instalasi tidak disertakan di repo publik. Untuk kondisi instalasi sendiri, gunakan Diagnostik, uji koneksi, log server dan hasil tahap proyek.

# Agen Mini 0.11.1 — private testing

First-run setup asks Local or Online before showing relevant connection choices.
Advanced harness, bot, password and swap options remain available in a collapsed section.
A connection must pass a real response check before setup is marked complete.
Loopback model endpoints can work without an invented API key.

Provider errors are categorized without exposing raw upstream payloads.
Provider-wide free-access limits pause that provider across model aliases and
skip redundant retries during the same turn. Other providers remain eligible.
Free access is subject to provider restrictions and is not guaranteed.

Native Linux code tools now use the bundled Python and its libraries; numerical
libraries use bounded thread counts. The installed-package check exercises plotting.

English README and website source feature the recorded small-model video-editor
benchmark with original imagery, measured exports and explicit provenance.
Coffee links use one custom vector badge and retain the owner's Tako URL.

The repository remains private and public website deployment is disabled.

# Agen Mini 0.11.0

Website download resmi dengan pilihan sistem, arsitektur, aplikasi dan CLI.
Link dihasilkan dari aset rilis nyata; format yang tidak tersedia tidak ditawarkan.
Paket desktop Linux baru: .deb amd64/arm64, .rpm x86_64/aarch64,
Arch .pkg.tar.zst x86_64, dan portable GNU/Linux glibc 2.35+.
Windows menyediakan installer EXE serta ZIP portable dengan agenmini.cmd.

Paket Linux menyertakan Python privat dan gateway Go. Tidak mengubah Python
sistem, tidak menjalankan aplikasi sebagai root, dan tidak membundel bobot AI.
Data pengguna terpisah dan tetap dipertahankan saat paket dihapus/diperbarui.
API/provider/model tetap bisa diubah melalui Pengaturan dan CLI.

Label dukungan menjadi **Buy me a coffee** dengan tautan Tako pemilik yang sama.
Karya asli mulai rilis ini memakai **GPL-3.0-or-later**, sama dengan SweepDesk;
lisensi komponen pihak ketiga dipertahankan. Source disediakan bersama paket.

Panduan: [website](https://zwart04.github.io/agenmini/) ·
[Linux](CARA-PASANG-LINUX.md) · [Windows](CARA-PASANG-WINDOWS.txt) ·
[VPS](CARA-PASANG-VPS.txt) · [lisensi](LICENSE).

## 0.10.3

# Agen Mini 0.10.3

Pembuatan editor video satu klip memakai bagian kecil dengan pemeriksaan
perilaku, termasuk wiring kontrol dan inisialisasi. Konteks dependensi berisi
implementasi model yang sudah lulus, dengan batas ukuran; tidak memasukkan
kode jawaban dari evaluator. Perbaikan yang merusak sintaks dikembalikan.
Jalur ini dipakai bersama oleh lokal, API online dan router, melalui web
maupun Telegram. Pengaturan lama bernilai `0` tetap menonaktifkannya.

Kandidat gabungan Qwen 0.8B dan DeepSeek Coder 1.3B sudah lulus uji browser
impor, playback, trim, teks dan unduhan WebM, termasuk pembatalan/pemulihan.
Video hasil ekspor didekode untuk memeriksa durasi, gerakan, suara dan teks.
Ini hasil beberapa percobaan kelas 1B, bukan satu respons atau bukti semua
model kecil dapat menulis aplikasi apa pun. [Bukti dan batas](docs/LOCAL-APPS-EVAL.md).

## 0.10.2

Update web/CLI kini menampilkan status antrean dan proses supervisor. Pembaruan
serta pergantian runtime menunggu pekerjaan/pemasangan harness eksternal selesai.
Permintaan update divalidasi, dipublikasikan utuh, dan tidak menimpa antrean aktif.
Windows atau instalasi manual menyediakan tombol menuju installer resmi.

Auto-compact menjaga catatan kerja dan riwayat asli. Pemeriksaan kode menerima
patch beberapa baris untuk memperbaiki exception, dengan validasi dan rollback.
Tes yang sama dapat dijalankan lagi setelah perubahan berkas yang berhasil.
Web dan Telegram tetap memakai inti agen bersama.

Tautan dukungan pemilik tersedia di README, sidebar web, halaman Update, serta
`agen dukung` / `python -m app.cli dukung`. Tidak menambah layanan atau dependensi.

Pengujian UI memakai data terpisah pada desktop/mobile dan kedua tema.
Pemeriksaan keamanan mencakup autentikasi/origin, izin runtime, isolasi kredensial,
antrean update dan pemindaian rahasia. Tidak mengakses VPS atau akun provider.
Runtime eksternal dengan akses penuh tetap memiliki alat/izin sendiri.

Benchmark video editor kelas 1B belum dinyatakan selesai: lolos tes fungsi ekspor
belum membuktikan aplikasi lengkap bekerja di browser. Tidak ada klaim model
kecil setara model besar atau training bobot baru.

# Agen Mini 0.10.1

- Maskot gelap otomatis di tema terang; satu PNG transparan.
- Koreksi self-improve dicari sesuai scope ingatan bot; rahasia disaring.
- App yang belum teruji perilakunya tidak dijadikan skill terverifikasi.
- Proteksi origin browser dan throttle login terhadap forwarded header palsu.
- Packaging menolak berkas privat/symlink; secret scan otomatis di GitHub.
- Peta folder; tes reusable dan tool lokal dipertahankan.

# Agen Mini 0.10.0

Harness bawaan mengadaptasi inti kontrol DeepSeek ke Python: tindakan alat berurutan, identitas call/result, journal privat, deadline dan penanganan tindakan terputus tanpa replay otomatis. Mode Kosong tetap terpisah; runtime DeepSeek asli tetap pilihan eksternal yang dipasang saat dipilih. Atribusi MIT dan commit sumber disertakan dalam paket.

Panggilan alat tidak lagi terpotong diam-diam pada tiga panggilan pertama. Batch dibatasi delapan secara eksplisit; tindakan yang ditunda tercatat parsial sampai benar-benar dijalankan. Jalur edit proyek Windows dinormalisasi agar folder tidak terduplikasi; editor JS membaca HTML aktual.

Chat mendapat Panel kerja dengan editor ringan, perubahan sebelum/sesudah, draf kode langsung, preview offline terisolasi, Browser dan log. Editor menolak konflik dengan perubahan agen dan membuat salinan sebelum menyimpan. Preview memakai browser pengguna; panel Browser bukan mesin otomatisasi agen. Import module, backend dan situs yang menolak iframe memerlukan server/tab tersendiri. Model dan akses alat dapat dipilih pada chat.

Maskot dari aset pengguna dibersihkan menjadi PNG transparan dan dianimasikan melalui CSS saat bekerja. Panel diperiksa pada desktop dan mobile 390 px, dengan kontrol custom, fokus modal dan dukungan reduced motion. Tidak menambah Monaco, Node service atau server animasi.

Pemasang memperbaiki 404 pada rilis 0.9.0: placeholder versi URL gateway diganti saat packaging; binary dan SHA256 diunduh ke staging sebelum mengganti binary lama. Instalasi di atas versi lama mempertahankan data/model/akun. README serta panduan pasang, update dan remove ditulis ulang.

Uji model lokal CPU 0.8B/1.2B memakai tugas converter gambar dan editor teks, bukan landing page atau template hasil. Ditemukan keluaran terpotong, sintaks salah dan kontrak HTML/JS salah. Guard membatasi perbaikan, memvalidasi tiap berkas, dan menolak menyimpan proyek yang belum valid. Detail hasil serta batas kualitas model ada di VALIDATION.md. Tidak ada klaim training bobot atau kemampuan setara model besar.

Publikasi mensyaratkan GitHub Actions Linux, installer Windows nyata dan matriks CLI upstream pada commit yang sama. Pengujian tidak mengakses VPS atau akun provider pengguna.

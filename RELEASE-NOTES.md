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

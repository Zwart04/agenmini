# Agen Mini

Asisten AI dengan chat web, Telegram, tim bot dan proyek bertahap. Agen Mini memakai HTML/CSS/JavaScript ringan tanpa framework antarmuka. Pilih model lokal melalui llama.cpp, 9router, FreeLLMAPI, API kompatibel OpenAI, atau gabungkan sumber dengan Smart Router.

**Versi stabil: 0.5.5.** Unduh pemasang dari [GitHub Releases](https://github.com/Zwart04/agenmini/releases/latest).

## Pasang di VPS Debian / Ubuntu

Jalankan sebagai root pada VPS yang mendukung Docker:

```bash
curl -fL https://github.com/Zwart04/agenmini/releases/latest/download/pasang-vps.sh -o pasang-vps.sh
curl -fL https://github.com/Zwart04/agenmini/releases/latest/download/pasang-vps.sha256 -o pasang-vps.sha256
sha256sum -c pasang-vps.sha256 && bash pasang-vps.sh
```

Alternatif: ekstrak `agenmini-vps.zip`, lalu jalankan `bash pasang-vps.sh`. Pemasang menyiapkan Docker/Compose jika diperlukan dan menampilkan alamat serta sandi. Buka TCP 443 pada firewall VPS. Sertifikat awal bersifat self-signed; browser meminta konfirmasi sertifikat.

Setup awal menawarkan lokal, 9router, FreeLLMAPI, keduanya, atau API langsung. Layanan tambahan bersifat opsional. Untuk pemasangan tanpa prompt: `AGEN_AI_PROFILE=online AGEN_OTOMATIS=1 bash pasang-vps.sh` (profil: `local`, `router`, `free`, `both`, `online`).

Mode API lebih ringan; 2 GB RAM disarankan. Untuk model lokal kecil, mulai dari 4 GB RAM dan 2 CPU. Anggaran model diperiksa dari RAM aktual; kebutuhan disk dan kecepatan bergantung model. Semua bot lokal berbagi satu model aktif, tanpa daemon Ollama. Build dan panggilan lokal berjalan serial untuk membatasi pemakaian RAM.

## Pasang di Windows

Unduh `agenmini-setup-0.5.5-windows-x64.exe` dari halaman release. Jalankan wizard pemasangan dan buka Agen Mini dari menu Start. Data disimpan terpisah di `%LOCALAPPDATA%\AgenMini\data`. Ini pemasang aplikasi, bukan ZIP portable.

Windows native dapat memakai API yang sudah berjalan. Pengelolaan layanan model lokal, 9router dan FreeLLMAPI memerlukan lingkungan Linux/WSL/Docker. Lihat [panduan Windows](CARA-PASANG-WINDOWS.txt).

## Mulai menggunakan

1. Buka **Koneksi**, pilih sumber AI, isi API key atau selesaikan OAuth yang didukung provider. Untuk lokal, pilih model yang sesuai RAM dan tunggu unduh, verifikasi hash serta status siap.
2. Klik **Uji koneksi**, lalu pilih model. Konfigurasi tersimpan belum berarti provider memiliki kuota atau model berhasil menjawab.
3. Buka **Chat** dengan Orchestrator. Berikan tujuan, jenis hasil dan kriteria penerimaan yang jelas. Model percakapan dapat dipilih pada chat; bot dapat memiliki pilihan sendiri.
4. Untuk pekerjaan bertahap, buat proyek di **Workspace**. Periksa tahap, hasil tes dan log; jeda atau lanjutkan dari checkpoint. Proyek berpindah ke Selesai setelah tahapnya lulus. Unduh source ZIP dari kartu hasil.
5. Hubungkan Telegram pada **Pengaturan**. Bot utama memakai Orchestrator. Gunakan `/model` untuk memilih sumber/model; riwayat Telegram dapat disalin ke web untuk dilanjutkan.

## Empat menu

| Menu | Fungsi |
| --- | --- |
| Chat | Percakapan, pilihan model, aktivitas alat, riwayat dan unduhan berkas |
| Workspace | Kantor tim bergerak, proyek aktif/selesai, aktivitas, diskusi, token, tim bot dan jadwal |
| Koneksi | Sumber AI, Smart Router, akun host, akun sosial dan MCP |
| Pengaturan | Preferensi, izin tindakan, Telegram, skill, ingatan, backup, update dan diagnostik |

Bagian utama tetap terlihat. Daftar aktivitas, skill dan ingatan memakai halaman ringkas; tombol **Baca lengkap** membuka rincian. Kantor memakai karakter CSS original dengan aksesori dan bubble, bukan aset milik Apple/OpenAI/Grok. Gerakan mengikuti aktivitas server; animasi dan polling dijeda ketika tab tersembunyi.

## Model, alat dan proyek

Smart Router memilih kandidat dari sumber yang terhubung dan mencoba cadangan secara serial ketika permintaan gagal. Model serta sumber aktual dicatat; kuota dan kemampuan tetap mengikuti provider. 9router opsional memakai backend Go yang dipin. Dashboard dapat dibuka melalui sesi Agen Mini tanpa membuka port router ke publik.

Alat meliputi Python, shell, berkas, pencarian/pembacaan web, memori, jadwal, MCP dan delegasi. Orchestrator dapat membuat spesialis dengan izin yang ditentukan, menugaskan pekerjaan dan meminta review. Hasil alat gagal tetap ditandai gagal; checkpoint memerlukan bukti berkas dan tes nyata. Mode **Akses penuh** tersedia di Pengaturan untuk alat yang telah diberikan kepada bot.

Skill menyediakan prosedur desain, coding, anti-slop dan verifikasi; dapat diedit atau diimpor sebagai Markdown. Diskusi tim saat senggang bersifat opsional, termasuk interval satu jam. Saran disimpan sebagai draft; menyimpan pelajaran memperbarui ingatan/prosedur, bukan melatih bobot model. Token berasal dari laporan provider. Biaya merupakan estimasi berdasarkan tarif yang diisi dan kurs bertanggal.

GitHub/Cloudflare dapat mendeteksi kredensial host yang tersedia dan memverifikasi akses. Keberadaan CLI saja tidak berarti akun terhubung. Threads, Instagram profesional, Meta Ads dan YouTube memerlukan aplikasi developer serta izin API resmi. MCP HTTP/stdio memerlukan server dan kredensial yang sesuai; executable stdio harus tersedia pada runtime. Fitur tidak mengaku tersambung hanya karena formulir sudah diisi.

Model kecil maupun API dapat salah. Tidak ada jaminan semua aplikasi kompleks selesai otomatis. Kapasitas model, dependensi proyek, RAM, kredensial dan kriteria penerimaan menentukan hasil. Untuk proyek besar, gunakan tahap kecil dengan build/test yang dapat diperiksa. Lihat [panduan proyek](PROYEK-BESAR.md), [katalog model](MODEL-CATALOG.md), dan [validasi serta batas pengujian](VALIDATION.md).

## Update, backup dan pengelolaan

Jalankan `sudo agen update`, atau ulangi pemasang versi baru. Update mempertahankan `.env`, data, sandi, bot, skill, MCP, riwayat dan konfigurasi provider. Supervisor memeriksa checksum, mencadangkan kode/database dan menunda update saat sibuk. Update otomatis harus diaktifkan sendiri.

Perintah umum: `agen status`, `agen log`, `agen restart`, `agen sandi`, `agen router-log`, `agen lokal-log`, `agen supervisor-log`.

Data VPS berada di `/opt/agenmini/data`. Unduh backup migrasi melalui Pengaturan sebelum reinstall VPS. Backup berisi data privat; simpan terpisah dari repo publik. Pemulihan serta pemasangan dijelaskan di [panduan VPS](CARA-PASANG-VPS.txt).

Hapus layanan sambil menyimpan data: `sudo agen uninstall --yes`. Periksa rencana penghapusan total: `sudo agen uninstall --all --dry-run`. Hapus seluruh Agen Mini **termasuk data dan model**: `sudo agen uninstall --all --yes`. Login host dan aplikasi VPS lain tidak termasuk penghapusan.

## Pengembangan

Gunakan Python 3.12, Node untuk pemeriksaan JavaScript dan dependensi pada `requirements.lock`. Jalankan regresi dengan direktori data terpisah:

```bash
python -m pip install -r requirements.lock pytest pytest-asyncio
DATA_DIR=/tmp/agenmini-tests PYTHONPATH=. python -m pytest -q
python build_release.py
```

Build release memakai berkas Git yang terlacak; ZIP diperiksa CRC dan SHA256. CI menjalankan regresi Linux dan siklus pemasangan/update/uninstall Windows sebelum publikasi. Jangan commit `.env`, database, kredensial, log pribadi, folder data atau bobot model.

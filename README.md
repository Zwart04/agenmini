# Agen Mini 0.3.2

Asisten pribadi ringan dengan web, Telegram, MCP, skill, memori, dan workspace bot.

## Instalasi paling mudah

Unduh `agenmini-vps.zip` dari [Releases](https://github.com/Zwart04/agenmini/releases/latest).
Ekstrak di komputer dan unggah `pasang-vps.sh` ke `/root` VPS Ubuntu/Debian.
Jalankan `bash /root/pasang-vps.sh` sebagai root. Pemasang memasang Docker/Compose,
membangun aplikasi, dan menampilkan URL serta kata sandi. Update menggunakan
perintah yang sama dan mempertahankan data. Lupa sandi: `agen sandi`.

Buka **AI & 9router**, hubungkan API key/OAuth provider, lalu pilih model.
Kunci router dibuat dan disimpan server secara otomatis. Semua pengaturan ada
pada satu aplikasi; provider OAuth masih memerlukan halaman login provider.
9router upstream digunakan sebagai container, bukan fork yang mengaku lebih kecil.

Pilihan **Lokal tanpa Ollama** membaca RAM host, RAM tersedia, CPU dan memori model yang dapat dilepas. Pilih rekomendasi atau model di katalog QwenPaw/Qwen3.5 0.8B-9B Q4. Mesin llama.cpp memakai CPU, konteks 4096, 1-4 thread dan satu permintaan; model yang melampaui anggaran RAM dibatasi. Unduhan pertama membutuhkan
internet dan sekitar 1.3 GB disk. Gunakan VPS 4 GB RAM untuk lokal; 2 GB disarankan
untuk mode API. CPU VPS menentukan kecepatan. Model kecil tetap bisa salah;
penjaga validasi alat dan sumber tidak menggantikan evaluasi model nyata.

## Menu

- **Workspace**: karakter CSS dengan bentuk/aksesori bervariasi, tugas aktif,
  log percakapan dan hasil alat, antrean persisten. Konsultasi antarbot dibatasi
  kedalaman dan hanya alat baca; satu worker membatasi antrean dan gate menserialkan inferensi. Tugas langsung dari pemilik memakai izin bot tujuan; tindakan sensitif menampilkan tombol Izinkan/Tolak di kantor.
- **Skill**: bawaan anti-slop, pemecahan masalah, desain bersih, verifikasi sumber; tambah/edit/import Markdown dan simpan prosedur dari hasil yang
  dikonfirmasi. Telegram menyediakan koreksi eksplisit dan Simpan cara kerja.
  Ingatan/prosedur berubah; bobot model tidak dilatih otomatis.
- **Koneksi MCP**: MCP lokal bawaan untuk hardware/pencarian skill, preset GitHub, HTTP/stdio, token, discovery, allowlist, alat baca, bot tujuan.
  Untuk GitHub/email gunakan server MCP yang sesuai dan izin akun Anda.
  Executable MCP stdio harus tersedia dalam image; HTTP tidak memerlukan Node.
- **Versi & Update**: rilis GitHub, instal manual atau otomatis harian. Host
  memeriksa SHA256, mencadangkan SQLite/kode, dan menunda saat model sibuk.
  Auto-update nonaktif sampai diaktifkan. Rollback kode mencoba build lama;
  backup data tersedia untuk pemulihan manual jika diperlukan.

## Pengelolaan

`agen status`, `agen log`, `agen router-log`, `agen lokal-log`, `agen update`,
`agen restart`, `agen sandi`. Data berada di `/opt/agenmini/data`.
Port publik default 443; port router hanya loopback. Sertifikat awal self-signed.
Kredensial berada di `.env`/data; jangan commit atau membagikannya.

Lihat [CARA-PASANG-VPS.txt](CARA-PASANG-VPS.txt) dan [VALIDATION.md](VALIDATION.md).

## Pengembangan

Python 3.12, `pip install -r requirements.lock`, `python -m app.main`.
Atur DATA_DIR, WEB_PASSWORD, WEB_TLS=0 untuk pengembangan lokal.
`pytest tests -q` (alat shell sandbox menggunakan Linux).
`python build_installer.py` menghasilkan pemasang self-extracting.
Karakter mengadaptasi ekspor SVG Dots Lab dengan bentuk/ekspresi dan aksesori lokal (atribusi di app/static/dots/CREDITS.txt); tidak ada paket gambar/font eksternal.

Dependensi: [9router](https://github.com/decolua/9router),
[llama.cpp](https://github.com/ggml-org/llama.cpp),
[QwenPaw Flash](https://huggingface.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M).
Lisensi dependensi/model mengikuti proyek masing-masing.


Model terkurasi diverifikasi metadata/berkasnya pada 2 Oktober 2026, bukan daftar otomatis semua model terbaru. Baca [MODEL-CATALOG.md](MODEL-CATALOG.md). Hanya QwenPaw 2B yang sudah menjalani smoke test inferensi di lingkungan ini; keluarga lain perlu diuji pada VPS Anda. Seed skill adalah prosedur Agen Mini, bukan pemasangan plugin Superpowers pihak ketiga.


### 0.3.2: status model dan tim

Empat menu utama: Chat, Workspace, Koneksi, Pengaturan. Workspace → Tim bot untuk memilih mesin/model setiap bot; semua bot lokal berbagi satu model, sedangkan bot API dapat memakai model berbeda pada provider yang terhubung. Orchestrator dapat berkonsultasi dengan semua spesialis yang terdaftar; konsultasi antarbot tetap baca saja dan dibatasi agar ringan.

Koneksi → AI menampilkan unduhan dalam byte/persen, verifikasi SHA256, pemuatan, status siap aktual dan log lokal. Pilihan yang tersimpan belum berarti model siap. Tidak perlu menghapus aplikasi atau cache model lama. Mode teks tidak memuat proyektor gambar. Jika gagal: agen lokal-log dan agen supervisor-log. Klik Unduh / perbaiki setelah melihat sebabnya.

FreeLLMAPI merupakan profil opsional di Koneksi, dengan akun internal dan kunci penghubung otomatis. Tambahkan API key provider; daftar model berasal dari server yang terhubung, bukan daftar model rekaan. auto:smart/auto:fast adalah strategi routing, dan nama slot Claude di upstream adalah alias kompatibilitas, bukan klaim model Claude asli. Model yang benar-benar melayani permintaan dicatat pada metadata jawaban. Kuota/ketentuan layanan provider tetap berlaku; akun berbayar Premium tidak diperlukan untuk integrasi ini.

Versi 0.3.2 mengganti skrip supervisor/CLI lewat rename atomik agar updater yang sedang berjalan tetap membaca berkas lamanya. Jika updater lama melaporkan potongan perintah setelah update, gunakan pemasang rilis dengan checksum seperti panduan CARA-PASANG-VPS.txt; data dan sandi dipertahankan. Tampilan ponsel diperiksa pada 320/390/430px, dengan menu yang dapat ditutup dari area luar, pilihan mesin dua kolom dan dialog yang dapat digulir.

# Agen Mini 0.5.4

Instruksi pemilik: **Orbit-Router dilindungi dan dikecualikan dari perbaikan otomatis**. Aturan lengkap ada di [AGENTS.md](AGENTS.md).

Empat halaman utama: Chat, Workspace, Koneksi, Pengaturan. Tim bot/jadwal, MCP, skill/ingatan/update/diagnostik digabung ke halaman induknya sebagai bagian yang langsung terlihat, tanpa accordion. Kantor tetap tampil; pemilihan provider dan formulir yang sedang diisi dipertahankan saat polling. Proyek yang lulus seluruh tahap pindah ke Selesai. Proyek mendukung nama/tujuan, ubah dan hapus catatan; source/repo/ZIP tidak ikut dihapus. Aktivitas bisa diubah selama masih antre, dihapus satu per satu, atau dibersihkan termasuk log/diskusi kantor; tugas berjalan dan chat web/Telegram tetap ada.

Perbaikan worker: path perintah relatif terhadap proyek, pembacaan source bertahap, galat alat menyertakan bagian akhir log, retry manual memulai ulang anggaran retry, dan JSON log panjang tetap valid. Build/test harus benar-benar exit0 sebelum checkpoint maju. ZIP proyek mengecualikan SQLite WAL/SHM dan berkas privat; pengecualian dan batas ukuran tercatat dalam manifest. ID proyek baru tidak menggunakan ulang folder atau arsip yang dipertahankan setelah catatan dihapus.

Hapus layanan saja sambil menyimpan data: `sudo agen uninstall --yes`. Hapus seluruh Agen Mini termasuk data, sandi, model dan konfigurasi provider: `sudo agen uninstall --all --yes`. Periksa rencana tanpa menghapus: `sudo agen uninstall --all --dry-run`. Docker, aplikasi lain, dan login akun host tidak dihapus.

9router opsional kini memakai backend Go yang dipin digest dan panel koneksi HTML/CSS/JavaScript bawaan. Akun upstream dipertahankan dengan backup SQLite sebelum migrasi; image khusus tetap dipertahankan. Dashboard lanjutan memakai ikon SVG lokal tanpa Google Fonts. Layanan router hanya dipublikasikan pada loopback, API key/login diwajibkan, dan TLS ketat diaktifkan.

Login `gh auth login` di akun host pemasang dideteksi dan diverifikasi melalui GitHub. Cloudflare dideteksi dari API token environment atau login Wrangler; sertifikat Tunnel tidak disamakan dengan API token. Token berada di direktori privat yang tidak dapat dibaca pengguna sandbox; alat bawaan GitHub/Cloudflare hanya membaca API yang diizinkan. CLI lain dideteksi keberadaannya, bukan dianggap memiliki login valid. Pada Linux/macOS non-Docker, startup membaca akun host dan memilih alamat router localhost otomatis. `ROUTER_BASE` dapat mengganti alamat; dalam Docker, akun host disampaikan oleh supervisor dengan snapshot privat. Pemasang Windows EXE dipasang dan diuji melalui CI Windows; pemasang VPS menargetkan Debian/Ubuntu.

Pengaturan menyediakan unduhan backup migrasi privat; pada host buat ulang dengan `python3 /opt/agenmini/make_vps_backup.py`. Backup adalah snapshot bertanggal, bukan sinkronisasi otomatis. Sebelum reinstall VPS, unduh backup privat `.env`, data aplikasi, database router dan FreeLLMAPI. Model bisa diunduh ulang. Jangan mempublikasikan arsip ini; akun host harus login ulang atau dipulihkan dengan aman pada VPS baru.

# Agen Mini

Asisten pribadi ringan dengan web, Telegram, MCP, skill, memori, dan workspace bot.

## Instalasi paling mudah

Unduh `agenmini-vps.zip` dari [Releases](https://github.com/Zwart04/agenmini/releases/latest).
Ekstrak di komputer dan unggah `pasang-vps.sh` ke `/root` VPS Ubuntu/Debian.
Jalankan `bash /root/pasang-vps.sh` sebagai root. Pemasang memasang Docker/Compose,
membangun aplikasi, dan menampilkan URL serta kata sandi. Update menggunakan
perintah yang sama dan mempertahankan data. Lupa sandi: `agen sandi`.

Buka **Koneksi → AI**, hubungkan API key/OAuth provider, lalu pilih model.
Kunci router dibuat dan disimpan server secara otomatis. Semua pengaturan ada
pada satu aplikasi; provider OAuth masih memerlukan halaman login provider.
9router upstream digunakan sebagai container, bukan fork yang mengaku lebih kecil.

Pilihan **Lokal tanpa Ollama** membaca RAM host, RAM tersedia, CPU dan memori model yang dapat dilepas. Pilih rekomendasi atau model di katalog QwenPaw/Qwen3.5 0.8B-9B Q4. Mesin llama.cpp memakai CPU, konteks 4096, 1-4 thread dan satu permintaan; model yang melampaui anggaran RAM dibatasi. Unduhan pertama membutuhkan
internet dan sekitar 0.58–6.17 GB disk sesuai model. Gunakan VPS 4 GB RAM untuk lokal; 2 GB disarankan
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


Model terkurasi diverifikasi metadata/berkasnya pada 2 Oktober 2026, bukan daftar otomatis semua model terbaru. Baca [MODEL-CATALOG.md](MODEL-CATALOG.md). QwenPaw 2B dan Qwen3.5 0.8B sudah menjalani smoke test inferensi di lingkungan ini; ukuran lain perlu diuji pada VPS Anda. Seed skill adalah prosedur Agen Mini, bukan pemasangan plugin Superpowers pihak ketiga.


### 0.3.2: status model dan tim

Empat menu utama: Chat, Workspace, Koneksi, Pengaturan. Workspace → Tim bot untuk memilih mesin/model setiap bot; semua bot lokal berbagi satu model, sedangkan bot API dapat memakai model berbeda pada provider yang terhubung. Orchestrator dapat berkonsultasi dengan semua spesialis yang terdaftar; konsultasi antarbot tetap baca saja dan dibatasi agar ringan.

Koneksi → AI menampilkan unduhan dalam byte/persen, verifikasi SHA256, pemuatan, status siap aktual dan log lokal. Pilihan yang tersimpan belum berarti model siap. Tidak perlu menghapus aplikasi atau cache model lama. Mode teks tidak memuat proyektor gambar. Jika gagal: agen lokal-log dan agen supervisor-log. Klik Unduh / perbaiki setelah melihat sebabnya.

FreeLLMAPI merupakan profil opsional di Koneksi, dengan akun internal dan kunci penghubung otomatis. Tambahkan API key provider; daftar model berasal dari server yang terhubung, bukan daftar model rekaan. auto:smart/auto:fast adalah strategi routing, dan nama slot Claude di upstream adalah alias kompatibilitas, bukan klaim model Claude asli. Model yang benar-benar melayani permintaan dicatat pada metadata jawaban. Kuota/ketentuan layanan provider tetap berlaku; akun berbayar Premium tidak diperlukan untuk integrasi ini.

Versi 0.3.2 mengganti skrip supervisor/CLI lewat rename atomik agar updater yang sedang berjalan tetap membaca berkas lamanya. Jika updater lama melaporkan potongan perintah setelah update, gunakan pemasang rilis dengan checksum seperti panduan CARA-PASANG-VPS.txt; data dan sandi dipertahankan. Tampilan ponsel diperiksa pada 320/390/430px, dengan menu yang dapat ditutup dari area luar, pilihan mesin dua kolom dan dialog yang dapat digulir.


### 0.3.3: aktivitas, model chat, dan coding

Animasi transform/opacity berjalan pada browser: menunggu, menulis, menggunakan alat, dan berbicara antarbot. Status datang dari SSE yang sudah ada; unduhan memakai byte nyata. Tab tersembunyi menjeda animasi/polling. Pengaturan menyediakan pilihan animasi aktif/nonaktif tanpa mengubah layanan VPS.

Pilih mesin/model di bar **Model chat**. Pilihan berlaku untuk percakapan tersebut; semua percakapan lokal tetap berbagi satu model agar hemat RAM. **Riwayat** menampilkan percakapan berbagai bot dan Telegram. Percakapan Telegram dapat disalin ke web dengan **Lanjutkan di sini**, sementara sumber tetap tersimpan. Di Telegram gunakan `/model`, `/model router`, `/model freellmapi`, `/model local`, atau `/model utama` untuk mengikuti bawaan bot.

**Koneksi → AI → Buka dashboard** membuka 9router/FreeLLMAPI melalui domain Agen Mini dengan sesi pemilik. Tidak perlu membuka port dashboard ke publik. **Tambah model Anda** membaca repo GGUF publik Hugging Face atau tag Ollama, mengunci revisi/hash, dan memeriksa RAM sebelum unduhan. Bobot Ollama dijalankan oleh llama.cpp; daemon Ollama tidak dipasang. Model split, privat, proyektor gambar, dan arsitektur yang tidak didukung llama.cpp tidak termasuk; model tambahan belum memiliki jaminan kualitas.

Pembuatan landing page memakai alat `build_website`: mode lokal membuat isi JSON pendek dengan schema, kemudian memakai layout HTML responsif bawaan. Model API menghasilkan HTML bebas. Berkas diperiksa dan otomatis dilampirkan; ini prototipe halaman, bukan aplikasi AI/payment yang sudah terhubung atau dipublikasikan. Coding lain tetap menggunakan berkas/Python/shell sesuai izin bot. Pengulangan alat yang gagal mempertahankan galatnya. **Pengaturan → Diagnostik → Uji alat inti** menjalankan pemeriksaan berkas, Python Linux, dan MCP hardware pada VPS Anda.

### 0.3.4: pemulihan runtime dan update VPS

Memilih ulang model lokal memulihkan layanan yang terputus. Readiness diperiksa dari health dan ID model aktual meskipun status kegagalan lama masih tersimpan. Anggaran Qwen3.5 0.8B CPU dikalibrasi menjadi 1400 MiB dengan cadangan host 700 MiB setelah inferensi nyata pada VPS 3,6 GiB; model lebih besar tetap dibatasi. Landing page mencatat model yang benar-benar melayani jawaban. Pemasang mencadangkan kode/SQLite, menerima instalasi FreeLLMAPI/API langsung, dan menyalakan layanan berdasarkan konfigurasi bot/percakapan yang tersimpan.

`python build_release.py` membuat ZIP pemasangan, ZIP source dari berkas Git, dan SHA256SUMS. Lihat VALIDATION.md untuk bukti VPS dan batas pengujian.

Pemasangan baru menyediakan setup awal: lokal saja, 9router saja, FreeLLMAPI saja, keduanya, atau API langsung. Untuk pemasangan otomatis gunakan `AGEN_AI_PROFILE=free AGEN_OTOMATIS=1 bash pasang-vps.sh` (nilai: `local`, `router`, `free`, `both`, `online`). Update mempertahankan pilihan di database dan `.env`; pilihan ini tidak mereset instalasi lama. Pada pilihan keduanya, image kedua disiapkan tetapi hanya mesin yang digunakan bot/percakapan yang dijalankan.

Kandidat ringan [9router-go](https://github.com/luqman-v1/9router-go) diuji terpisah: v1.9.7 binary idle RSS sekitar 32 MiB; image Docker teruji memakai sekitar 12 MiB cgroup. Integrasi dashboard/providers/combos memakai JWT kompatibel, tetapi `/api/models` menolak autentikasi adapter saat ini. Karena kompatibilitas model/akun belum lulus, fork ini belum menjadi opsi pemasang atau pengganti otomatis. Upstream yang dipin tetap tersedia secara opsional; instalasi FreeLLMAPI/API langsung tidak menjalankan 9router tanpa kebutuhan bot/chat.

### 0.3.5: tim pelaksana dan proyek bertahap

Orchestrator menugaskan pekerjaan nyata, membuat spesialis domain dengan izin terbatas, dan meminta review. Telegram utama memakai Orchestrator. Workspace menampilkan tim, aktivitas, proyek persisten dan checkpoint. Koneksi memandu setup dan uji lokal/9router/FreeLLMAPI/API langsung serta Smart Router milik Agen Mini. Unduhan HTML memakai nama berkas produk; coding memakai anggaran lebih besar, pemeriksaan dan layout interaktif yang hemat untuk lokal. Node/npm/git tersedia sebagai alat proyek, dengan build serial dan batas RAM. Baca [alur proyek besar dan batas pengujiannya](PROYEK-BESAR.md).

Workspace menampilkan kantor dengan karakter CSS original, meja kerja, ruang rapat untuk delegasi aktif, dan area tunggu. Gerakan mengikuti status server; animasi diam hanya menunjukkan kehadiran. Animasi/polling dijeda saat tab tersembunyi dan pilihan reduced motion dihormati. Aktivitas diringkas dengan detail lengkap yang bisa dibuka. Bersihkan aktivitas selesai hanya menghapus tugas kantor done/failed, bukan tugas aktif, percakapan atau berkas proyek. Izin proyek menampilkan perintah/folder/alasan sebelum diizinkan atau ditolak; tindakan berhasil melanjutkan checkpoint, kegagalan tetap ditandai gagal.

## Windows, akun resmi, dan kantor tim

Installer Windows x64 dipasang melalui wizard dan menu Start; data berada terpisah di `%LOCALAPPDATA%\AgenMini\data`. Panduan: [CARA-PASANG-WINDOWS.txt](CARA-PASANG-WINDOWS.txt). Runtime Python, Node dan MinGit disertakan dengan checksum upstream. Layanan model lokal/9router/FreeLLMAPI yang dikelola supervisor memerlukan Linux/WSL/Docker; Windows native dapat memakai API yang sudah berjalan.

Setup awal menyatukan sumber AI, deteksi akun host, OAuth Threads/Instagram profesional/Meta Ads/YouTube, dan MCP. Akun sosial memerlukan aplikasi developer dan izin resmi; login browser saja bukan akses API. Uji koneksi hanya membaca akun. Publikasi Threads/Instagram tersedia sebagai alat dengan izin tindakan; unggah YouTube dan perubahan iklan membutuhkan MCP yang sesuai.

Kantor memiliki empat ruang tim, gerakan dari aktivitas/delegasi aktual, bubble diskusi dan rincian yang bisa dibuka. Diskusi senggang opsional sekali sejam: tiga panggilan model serial pendek, tidak berjalan ketika antrean pemilik aktif. Saran adalah draft; pelajaran baru disimpan setelah ditinjau, bukan pelatihan bobot. Angka token hanya berasal dari usage provider. Biaya memerlukan tarif model yang diisi pemilik; angka tanpa tarif ditandai belum diketahui. Konversi mata uang memakai kurs ECB bertanggal dan tersimpan, bukan tebakan AI.

Mode tindakan: **Pengaturan → Izin tindakan → Akses penuh**, lalu simpan. Mode ini melewati tinjauan alat yang telah diberikan kepada bot dan melanjutkan checkpoint proyek yang menunggu izin. Instalasi baru memakai mode tinjauan; kredensial, ruang kerja, dan pembuktian hasil tetap berlaku.

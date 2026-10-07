# Harness asli, dipasang seperlunya

Agen Mini menawarkan inti bawaan ringan dan distribusi CLI upstream asli yang opsional. **Agen Mini · inti DeepSeek** mengadaptasi kontrak lifecycle dan eksekusi alat DeepSeek ke Python: log call/result, alat serial, deadline dan penanganan tindakan terputus. Ini bukan runtime `dsh` asli atau port lengkap. Sumber, lisensi dan batas adaptasi ada di [DEEPSEEK-CORE.md](DEEPSEEK-CORE.md). Katalog tidak memasang apa pun saat dibaca.

## Memilih

1. Di setup awal, pilih isi awal **Kosong** atau **Paket bawaan**, lalu pilih harness secara terpisah. Kosong tidak mengisi skill, ingatan atau MCP; harness Kosong menghilangkan prompt bawaan dan konteks otomatis.
2. Instalasi yang sudah dipakai: **Pengaturan → Umum → Cara kerja & belajar → Harness**. Pilih runtime, lalu **Pasang & gunakan**, atau simpan formulir pengaturan.
3. Tunggu indikator pemasangan. Paket hanya aktif setelah CLI upstream berhasil menjalankan pemeriksaan `--help`. Galat pemasangan terlihat dan dapat dicoba ulang. **Batalkan** menghentikan grup proses pemasang; instalasi tidak lengkap tidak dipakai.
4. Buka **Model & kredensial runtime**, isi ID model dan API key milik Anda, lalu simpan. Provider/model harus mengikuti dokumentasi runtime tersebut. Untuk Pi/oh-my-pi gunakan provider seperti `openai` atau `anthropic`; OpenCode memakai `provider/model`.
5. Runtime eksternal memiliki alat sendiri. Aktifkan **Akses penuh** secara sadar sebelum menjalankan chat. Izin alat per bot Agen Mini tidak membatasi CLI upstream. Jika tidak diaktifkan, chat menampilkan penjelasan dan tidak menjalankan runtime.
6. Chat teks di web dan Telegram menjalankan CLI terpilih. Model runtime dapat diganti per percakapan melalui Terapkan pada chat web atau `/model ID_MODEL` di Telegram; provider/key tetap mengikuti konfigurasi runtime. Riwayat delapan pesan terakhir dikirim sebagai konteks teks; jawaban CLI asli disimpan di riwayat Agen Mini. Proses dibatasi lima menit dan satu tugas bersamaan.

**Terpasang** berarti CLI lulus pemeriksaan, bukan provider telah menjawab. API key tersimpan bukan bukti koneksi atau kuota. Galat, respons kosong dan status error dalam JSON bukan sukses; tidak ada fallback tersembunyi ke agen bawaan.

## Runtime tersedia

| Pilihan | Distribusi asli yang dipasang | Kebutuhan / catatan |
| --- | --- | --- |
| Kosong | Tidak memasang paket tambahan | Tidak menyuntik prompt/panduan/konteks otomatis; protokol alat dan penjaga aplikasi tetap berjalan |
| Agen Mini · inti DeepSeek | Adaptasi Python bawaan aplikasi | Alat serial, lifecycle/log, integrasi delegasi, MCP, skill dan ingatan; tanpa CLI tambahan |
| [Hermes](https://github.com/nousresearch/hermes-agent) | Source commit `7157422022ff` dalam venv sendiri | Python 3.14 privat dipasang saat dipilih; provider/model asli; skill/ingatan Hermes terpisah |
| [OpenCode](https://github.com/anomalyco/opencode) | `opencode-ai@1.18.34` | Banyak provider, model `provider/id` |
| [Claude Code](https://code.claude.com/docs/en/headless) | `@anthropic-ai/claude-code@2.1.289` | Distribusi resmi; kode inti bukan open source untuk di-fork. Mode `--bare` memakai API key Anthropic |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | `@deepseek-ai/dsh@0.2.0-rc.2` | Developer preview; API key DeepSeek; model opsional mengubah patch pemilih model asli |
| [oh-my-pi](https://github.com/can1357/oh-my-pi) | `@oh-my-pi/pi-coding-agent@18.6.1` | Bun 1.3.14 (`--smol`) dipasang hanya untuk pilihan ini |
| [Pi](https://github.com/earendil-works/pi) | `@earendil-works/pi-coding-agent@1.0.3` | CLI ringkas, Node; provider/model asli |
| [Aider](https://github.com/Aider-AI/aider) | `aider-chat==0.86.2` | Python 3.10–3.12; venv sendiri, auto-commit dimatikan |
| [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) | `mini-swe-agent==2.4.6` | Loop shell/model asli; dependensi model Python terpisah |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `@google/gemini-cli@0.62.0` | API key Gemini; persetujuan native tetap berlaku |

Pin upstream disengaja supaya update aplikasi dapat diuji sebelum versi CLI diganti. Ini bukan janji setiap pin selalu versi upstream terbaru. Paket JavaScript memasang Node 24.21.0 privat saat dipilih; npm sistem hanya menjadi bootstrap. Paket Python memakai venv privat; Hermes terbaru memerlukan Python 3.14 dan mendapat interpreter privat melalui uv saat dipilih, tanpa mengganti Python aplikasi. Lisensi upstream tetap berlaku; aplikasi tidak menggandakan semua repo atau fork sebagai paket bawaan.

## Ringan dan transparan

Tidak ada daemon harness tambahan, dashboard kedua atau port baru. Hanya CLI terpilih dijalankan saat menerima chat. CLI, HOME, cache dan workspace masing-masing terpisah. Model, kunci, skill/MCP serta ingatan eksternal tidak otomatis disalin dari Agen Mini. Login OAuth CLI lewat terminal dan impor sesi native belum dijembatani oleh web; integrasi ini memakai API key eksplisit.

Runtime eksternal adalah opsional dan lebih besar daripada Agen Mini bawaan. Sediakan setidaknya 2 GB RAM untuk mode API, ruang disk tambahan untuk dependensi, dan container Agen Mini minimal 2 GB bila memakai harness eksternal. Installer default tidak menaikkan batas RAM diam-diam: atur `AGEN_MEM_LIMIT=2g` di `.env`, lalu jalankan `cd /opt/agenmini && docker compose --env-file .env --env-file data/local-runtime.env -f docker-compose.standalone.yml up -d agen` agar container dibuat ulang dengan batas baru. Pada Windows gunakan installer resmi yang menyertakan Python, Node/npm dan Git.

Output dibatasi 1 MB; proses chat CLI maksimal 512 MB RAM (oh-my-pi 768 MB dengan Bun `--smol`), pemasang maksimal 1 GB (oh-my-pi 1,5 GB saat pemasangan; Windows Job Object dan Linux memantau grup proses), timeout dan pembatalan membunuh turunannya. Paket yang membutuhkan lebih banyak resource akan gagal dengan pesan yang terlihat. Cache pemasangan tetap tersimpan saat kembali ke Agen Mini, sehingga tidak perlu unduh ulang. Semua versi dan status terlihat dalam pengaturan. Data dan kredensial privat tidak dimasukkan source ZIP.

## Batas izin dan fitur

CLI menjalankan alat dan kebijakan native, bukan definisi alat Agen Mini. Windows menjalankan CLI dengan hak akun Windows yang sedang memakai aplikasi; Job Object membatasi resource dan lifetime, **bukan sandbox filesystem**. Linux menurunkan proses pemasang dan runtime ke user kerja ketika aplikasi berjalan sebagai root. HOME/env dikosongkan dari token/login host; CLI tetap harus diperlakukan sebagai program pihak ketiga yang Anda izinkan. Ini tidak memberi jaminan isolasi semua berkas yang dapat dibaca user sistem tersebut.

Jembatan ini mendukung chat teks langsung. Lampiran, proyek bertahap dan konsultasi otomatis antarbot tidak dialihkan ke CLI eksternal karena izin alatnya berbeda. Kembali ke Agen Mini untuk fitur tersebut; jangan menganggap MCP atau learning Agen Mini sudah menjadi plugin native. Editor prompt di web berlaku pada agen bawaan; CLI eksternal memakai instruksi native masing-masing.

Fitur usulan perbaikan aplikasi tetap menghasilkan draft/diff/ZIP dan tidak memasang kode AI. Pilihan runtime tidak mengubah alur review → GitHub Actions → release. Jangan memberikan akses workspace source aktif kepada CLI bila Anda menginginkan perubahan melalui penjaga draft aplikasi.

## Pengujian

Workflow **Original harness runtimes** memasang setiap distribusi nyata pada runner Linux dan Windows terpisah, memeriksa CLI/headless flags serta memastikan hanya runtime terpilih yang diunduh. Ini tidak menguji akun provider berbayar atau menjamin kualitas suatu model. Workflow aplikasi menguji masking/env, izin, pembatalan, timeout, error JSON, mode Kosong dan larangan fallback tersembunyi. Linux diuji melalui GitHub Actions, bukan VPS pengguna.

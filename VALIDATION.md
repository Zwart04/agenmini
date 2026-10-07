# Validasi Agen Mini 0.10.0

## Inti DeepSeek dan panel kerja — 7 Oktober 2026

70 tes terkait agent, proyek, jalur model lokal, editor, journal dan sintaks frontend lulus di Windows lokal. Kasus mencakup tindakan mutasi terputus dengan outcome unknown tanpa replay, argumen privat tidak masuk log, penolakan jalur traversal/berkas privat, dan simpan editor yang konflik dengan perubahan agen. Pemeriksaan packaging memastikan placeholder URL gateway benar-benar diganti pada pemasang yang dibangun. CI Linux memeriksa seluruh suite serta fixture pemasang/supervisor; release gate memerlukan sukses pada commit rilis yang sama.

Browser nyata pada preview dengan data terpisah memeriksa simpan berkas dan tombol JavaScript di iframe preview. Pada desktop 1440×900 dan mobile 390×844, document scrollWidth sama dengan lebar viewport. Screenshot panel tersedia pada docs/screenshots/workbench-desktop-v010.jpg dan workbench-mobile-v010.jpg; berkas demo ditulis untuk pengujian editor, bukan bukti model menghasilkan aplikasi. Panel memakai textarea dan iframe native; tidak ada Monaco atau layanan render di VPS. RAM VPS belum diukur.

Evaluasi model CPU nyata dapat diulang memakai scripts/evaluate_apps.py. Data, draft dan laporan disimpan ke direktori temp baru; kode tidak diganti dengan template evaluator. Tugas converter mencakup unggah, canvas, resize dan download; editor mencakup file UTF-8, hitungan kata, replace-all dan save. Kanal tg memanggil agent.Turn yang sama, bukan Telegram network. Respons yang terpotong/invalid tetap failed. Hasil pengujian aplikasi model dicatat di docs/LOCAL-APPS-EVAL.md; sintaks/ZIP tidak membuktikan perilaku browser.

## Gateway koneksi

Pembaruan evaluasi 6 Oktober 2026: katalog memuat 90 provider chat. Browser nyata memeriksa logo OpenCode, kartu tanpa key, aktivasi sumber, pemilih model custom dan respons Uji koneksi OpenCode Free (`oc/muse-spark-1.3-contributor-free`, 23,4 detik). Ini bukti satu permintaan gratis, bukan jaminan kuota. Tampilan diuji pada 390×844 dan 1440×900: tidak ada overflow horizontal/galat console. Google OAuth memakai konfigurasi client aplikasi milik operator, tanpa client secret upstream di repository.

## Model CPU nyata, bukan fixture

Qwen3.5 0.8B Q4_K_M (579.615.840 byte; SHA256 `fb044e93939a70469c905781334f5de1e6c8b608ced6cbc8c9249bd4127d9526`) dan LiquidAI LFM2.5 1.2B Instruct QAD Q4_0 (695.755.488 byte; SHA256 `bb741ebb106d543e9de114b843a3d3d73d51c74b5801e69da2abde821a0cb3e1`) dijalankan melalui llama.cpp CPU b11443, 4 thread, konteks 8192, satu slot. Binary/model diunduh dari rilis/repository resminya dan disimpan terpisah dari data aplikasi. RSS LFM sekitar 1,4 GB saat uji; bukan jaminan RAM VPS.

Permintaan menggunakan nonce baru untuk berkas/produk. Jalur asli `agent.Turn` diuji untuk web dan Telegram, termasuk eksekusi Python nyata. **Tidak melatih bobot, tidak memakai hasil LLM mock, tidak mengganti HTML dengan template.** Perbandingan menunjukkan kegagalan aritmetika/format, count alih-alih sum, keluaran terpotong dan HTML dengan kontrol yang tidak sesuai brief. Percobaan yang awalnya tampak lulus ditemukan memiliki assertion di fungsi yang tidak dipanggil: pemeriksa kini mengeksekusi assertion secara terpisah, mempertahankan ekspresi saat repair, dan menolak perubahan tes. Hasil ini belum memenuhi standar coding otomatis yang andal; jangan menyebut model 1B setara model besar.

Perbaikan tambahan: JSON tool lokal dibatasi schema dan keluaran terpotong tidak dieksekusi; tes print-only tidak dianggap lulus; program baru memerlukan tinjauan sebelum eksekusi pada mode biasa; perbaikan dibatasi dua kali. HTML memeriksa beberapa kelalaian brief dan dialog bawaan, tetapi validasi struktur/sintaks diberi label berbeda dari uji interaksi. Setup satu bot tidak mendelegasikan ke spesialis template yang belum dipasang. Script `scripts/evaluate_local.py` merekam uji nyata dan menjalankan enam assertion evaluator untuk fungsi contoh, termasuk input yang tidak ada pada brief model. Tidak menguji pengiriman jaringan Telegram atau autentikasi setiap provider.

Satu alur berkas sederhana Qwen 0.8B lulus dengan nonce baru: `write_file` membuat isi persis yang diminta dan `read_file` membaca ulang, 31,4 detik. Berkas juga diperiksa langsung oleh evaluator. Argumen nama berkas digrounding ke nama eksplisit pada permintaan dan penulisan dilakukan sebelum baca ulang. Ini membuktikan alur tersebut, bukan seluruh alat atau kualitas coding kompleks. [Laporan aktual](docs/qa/local-qwen08-real.json) mencantumkan trace dan keluaran model; laporan coding gagal disertakan agar hasil tidak dipilih hanya yang berhasil.

65 tes agent/backend/bridge/kontrol/frontend/arsip lulus pada Windows setelah perbaikan guard awal. Suite coding tambahan: 75 lulus, satu asumsi shell POSIX (`false | tail`) gagal di Windows dan diuji pada Linux Actions. Tes baru mencakup assertion tersembunyi, isolasi data evaluasi dan JSON terpotong. Hasil CI pada commit rilis menjadi acuan pemeriksaan Linux, installer Windows dan matriks runtime.

## Kontrak gateway dan pemasangan

Fork Go dijalankan sebagai proses nyata dengan direktori dan kredensial disposable. Pemeriksaan mencakup autentikasi admin/API, pembuatan key, daftar koneksi tanpa key privat, katalog model, awal PKCE, dan penolakan endpoint fitur yang dibuang. Tes bridge memeriksa session device login tetap di server dan akun API dibaca dari endpoint koneksi lengkap. Tes installer memastikan byte PNG logo tidak rusak oleh normalisasi baris.

30 tes kontrol/bridge/frontend/arsip lulus di Windows lokal. Seluruh suite juga dicoba: 257 lulus, 10 gagal pada asumsi shell, izin POSIX, discovery atau supervisor Linux di Windows. Pemeriksaan Linux wajib menggunakan Actions sebelum publikasi. Keberhasilan fixture bukan bukti login atau kuota semua provider. Binary Windows diuji mandiri; pengelolaan gateway otomatis dari wizard Windows belum tersedia, gunakan endpoint gateway yang sudah berjalan.

Gateway tidak menjalankan dashboard kedua, rute media, terminal, analitik, relay atau updater mandiri. Sumber upstream dan lisensi MIT disimpan pada gateway/UPSTREAM.json dan gateway/LICENSE. Harness CLI asli belum diubah menjadi SDK pada rilis ini.

Setup tambahan diuji: Orchestrator awal, template bot idempotent tanpa menimpa persona pengguna, rekomendasi swap berdasarkan RAM fisik, permintaan host dengan pilihan tetap, validasi sandi dan pencabutan sesi, serta larangan menghapus bot utama. Workflow host menggunakan perintah swap/Docker yang dimock di container disposable; tidak mengaktifkan swap nyata pada host atau VPS pengguna. Browser memeriksa posisi notifikasi dan modal template di desktop/mobile. Hardware pada screenshot setup menggunakan fixture preview.

## Runtime asli

Katalog menyediakan sembilan CLI upstream, diunduh hanya ketika dipilih. Workflow `harnesses.yml` memasang paket asli pada Linux dan Windows (18 kombinasi), menjalankan CLI dan memeriksa argumen headless. Uji Pi tambahan menjalankan alat `write` upstream dan memverifikasi berkas hasil serta lampiran unduhan; respons model pada uji tersebut berasal dari server fixture protokol, bukan model/provider nyata.

45 tes terkait harness/profil/penjaga/frontend lulus di Windows lokal. Kasus mencakup isolasi environment, masking kunci, mode Kosong, penolakan fallback, pembatalan/timeout, manifest rusak, izin native serta pemilihan model per percakapan web/Telegram. Release memerlukan keberhasilan workflow aplikasi Linux, installer Windows nyata dan seluruh matriks runtime pada commit yang sama. Bukti aktual tersedia melalui badge dan riwayat Actions.

Pemilih custom dan penjelasan runtime diperiksa pada desktop 1440 px dan mobile 390 px. Screenshot `runtime-desktop.jpg` dan `runtime-mobile.jpg` memakai data demo. Pengujian ini tidak menggunakan kredensial, akun provider atau VPS pengguna.

## Pemeriksaan

- Uji regresi mencakup alur agent, tools, proyek, izin, Telegram, API kontrol, memory dan backend. Workflow Linux menjalankan seluruh tests dan installer/supervisor sebelum rilis; Windows menjalankan pemasang EXE nyata beserta lifecycle native app.
- Tambahan uji terisolasi: setup kosong bertahan saat restart, paket bawaan tidak mengarang profil pemilik, karantina fakta preset lama, satu bukti alat memerlukan tinjauan, cache/galat/koreksi tidak dipromosikan, versi skill/rollback, skor rating idempotent, ekspor privat, batas discovery alat, respons Telegram dan write_file nyata.
- API setup/learning/export memerlukan sesi; pilihan setup dan konfirmasi ekspor eksplisit. Dataset deduplikasi/split tidak menimpa data lama. Jalur refleksi tidak melewati tinjauan skill.
- Di Windows lokal: 41 tes agent/profil/backend lulus, ditambah pemeriksaan kontrol/profil/frontend 38 tes dan 3 tes kontrak/syntax frontend (sebagian tumpang tindih; bukan dijumlahkan). Shell quote dan grafik Python diverifikasi dengan eksekusi kode nyata.
- Browser preview dengan data sendiri: setup Kosong, simpan mode belajar, tinjauan kandidat dari write_file nyata dan aktivasi skill. Pengaturan, Skill dan koneksi diperiksa pada 320/390/1280px (9 kombinasi tab/ukuran); tidak ada overflow horizontal atau galat JS. Tidak menjalankan model/provider pemilik.

## Perubahan terjaga dan dokumentasi visual

33 tes profil/pembelajaran/penjaga/frontend lulus pada Windows lokal. Pengujian baru mencakup revisi/reset/restore harness, pencarian FTS setelah edit ingatan, penolakan restore silang, autentikasi editor, versi skill manual, traversal/jalur penjaga, keluaran model yang rusak, ZIP draft nyata, source yang berubah, pembatalan dan proses yang terputus. Fixture model menguji kontrak; tidak membuktikan kualitas provider nyata.

Browser lokal memverifikasi instruksi tersimpan dan masuk ke prompt aktif. Workspace dengan 10 bot diperiksa pada viewport 390 px tanpa overflow horizontal; dropdown custom dan dialog diperiksa di desktop/mobile. Screenshot serta preview GIF/MP4 berasal dari data demo terpisah, tanpa percakapan atau kredensial pemilik. Preview tidak memperlihatkan model menjawab atau bot benar-benar bekerja.

Draft AI tidak dieksekusi, dipasang, atau menulis source aktif. Pemeriksaan draft memvalidasi jalur/ukuran/hash dan sintaks Python, bukan tes integrasi kode kandidat. Review keamanan dan CI branch tetap diperlukan. Pengujian Linux dilakukan melalui GitHub Actions pada Zwart04/agenmini; tidak mengakses VPS pengguna/kantor, akun Davdigi atau repo lain.

## Batas

Fixture model menguji kontrak dan penanganan hasil alat, bukan kecerdasan model. Tidak ada bobot baru dilatih, benchmark frontier atau jaminan bebas halusinasi. Training SFT jawaban tidak membuktikan tool-calling. Panduan training mencantumkan sumber primer dan proses evaluasi terpisah.

Belum menguji live VPS pengguna, pesan Telegram nyata atau OAuth/API akun pengguna. Data/model/kredensial lama tidak dihapus atau dipublikasikan. Gateway lama dipertahankan untuk kompatibilitas; layanan opsional tidak dijalankan jika tidak dibutuhkan.

## Komponen custom

26 tes proyek/profil/frontend lulus setelah memperbaiki perlombaan pembelajaran latar belakang dengan tugas baru. Seluruh pembelajaran background melewati pekerjaan aktif; status panggilan model gagal tidak ditulis sebagai selesai.

Dropdown custom dan popup konfirmasi/input diuji di browser: keyboard End/Enter/Escape, nilai form asli, nol select native terlihat, input ingatan tersimpan di data preview dan batal ekspor tidak mengunduh apa pun. Komponen memakai tema/desain dan tidak menambah runtime dependency. Uji statis memastikan tidak ada alert/confirm/prompt browser pada script produksi.

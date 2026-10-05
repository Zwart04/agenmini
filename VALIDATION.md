# Validasi Agen Mini 0.7.0

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

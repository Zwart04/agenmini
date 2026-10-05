# Validasi Agen Mini 0.7.0

## Pemeriksaan

- Uji regresi mencakup alur agent, tools, proyek, izin, Telegram, API kontrol, memory dan backend. Workflow Linux menjalankan seluruh tests dan installer/supervisor sebelum rilis; Windows menjalankan pemasang EXE nyata beserta lifecycle native app.
- Tambahan uji terisolasi: setup kosong bertahan saat restart, paket bawaan tidak mengarang profil pemilik, karantina fakta preset lama, satu bukti alat memerlukan tinjauan, cache/galat/koreksi tidak dipromosikan, versi skill/rollback, skor rating idempotent, ekspor privat, batas discovery alat, respons Telegram dan write_file nyata.
- API setup/learning/export memerlukan sesi; pilihan setup dan konfirmasi ekspor eksplisit. Dataset deduplikasi/split tidak menimpa data lama. Jalur refleksi tidak melewati tinjauan skill.
- Di Windows lokal: 41 tes agent/profil/backend lulus, ditambah pemeriksaan kontrol/profil/frontend 38 tes dan 3 tes kontrak/syntax frontend (sebagian tumpang tindih; bukan dijumlahkan). Shell quote dan grafik Python diverifikasi dengan eksekusi kode nyata.
- Browser preview dengan data sendiri: setup Kosong, simpan mode belajar, tinjauan kandidat dari write_file nyata dan aktivasi skill. Pengaturan, Skill dan koneksi diperiksa pada 320/390/1280px (9 kombinasi tab/ukuran); tidak ada overflow horizontal atau galat JS. Tidak menjalankan model/provider pemilik.

## Batas

Fixture model menguji kontrak dan penanganan hasil alat, bukan kecerdasan model. Tidak ada bobot baru dilatih, benchmark frontier atau jaminan bebas halusinasi. Training SFT jawaban tidak membuktikan tool-calling. Panduan training mencantumkan sumber primer dan proses evaluasi terpisah.

Belum menguji live VPS pengguna, pesan Telegram nyata atau OAuth/API akun pengguna. Data/model/kredensial lama tidak dihapus atau dipublikasikan. Gateway lama dipertahankan untuk kompatibilitas; layanan opsional tidak dijalankan jika tidak dibutuhkan.

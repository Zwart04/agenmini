# Agen Mini 0.9.0

Katalog 90 provider chat mencakup OpenCode Free/MiMo Free/Devin CLI tanpa API key, cookie dan impor Cursor. OpenCode Free diuji dengan respons nyata. OAuth Google memakai client aplikasi operator; akun provider lain belum seluruhnya diuji.

Uji nyata model CPU 0.8B/1.2B menemukan hasil coding belum andal. Guard kini menjalankan assertion tersembunyi, menolak perubahan tes saat repair, menolak JSON alat terpotong, dan membedakan validasi sintaks HTML dari perilaku browser. Setup satu Orchestrator tidak lagi mencoba bot template yang belum dipasang. Evaluasi dapat diulang melalui `scripts/evaluate_local.py`; tidak ada klaim training bobot atau kemampuan setara model besar.

Agen Mini Gateway adalah fork koneksi 9router-go berdasarkan 9router: OAuth, refresh, API key, model, streaming dan fallback berada dalam satu aplikasi. Dashboard kedua, media, terminal, analitik, relay dan updater router tidak dijalankan. Logo provider disimpan lokal dan dapat dicari di Pengaturan → Koneksi AI & model.

Menu utama menjadi Chat, Tugas & Tim, Pengaturan. Proyek dan aktivitas digabung pada Tugas; biaya dan diskusi tim berada pada bagian lanjutan. FreeLLMAPI tidak ditawarkan pada instalasi baru; konfigurasi lama dipertahankan.

Pemasang Linux mengambil binary Go sesuai arsitektur dan memeriksa SHA256 sebelum build container. Compiler Go/Node tidak dipasang di VPS. Database gateway managed lama dibackup sebelum migrasi; akun laptop dan VPS pengguna tidak disentuh saat pengembangan.

Perbaikan bridge mencakup endpoint OAuth Go, status authorized, daftar koneksi API lengkap, session device privat, dan callback beberapa metode login. Arsip installer mempertahankan byte logo PNG.

Pemeriksaan menggunakan binary gateway nyata dan kredensial fixture, bukan akun atau kuota provider pengguna. Gateway Windows tersedia sebagai binary mandiri; wizard Agen Mini Windows masih memakai endpoint gateway yang sudah berjalan. CLI harness asli belum diganti SDK. Hasil CI dan batas pengujian tersedia dalam VALIDATION.md.

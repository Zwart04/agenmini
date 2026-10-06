# Agen Mini 0.9.0

Agen Mini Gateway adalah fork koneksi 9router-go berdasarkan 9router: OAuth, refresh, API key, model, streaming dan fallback berada dalam satu aplikasi. Dashboard kedua, media, terminal, analitik, relay dan updater router tidak dijalankan. Logo provider disimpan lokal dan dapat dicari di Pengaturan → Koneksi AI & model.

Menu utama menjadi Chat, Tugas & Tim, Pengaturan. Proyek dan aktivitas digabung pada Tugas; biaya dan diskusi tim berada pada bagian lanjutan. FreeLLMAPI tidak ditawarkan pada instalasi baru; konfigurasi lama dipertahankan.

Pemasang Linux mengambil binary Go sesuai arsitektur dan memeriksa SHA256 sebelum build container. Compiler Go/Node tidak dipasang di VPS. Database gateway managed lama dibackup sebelum migrasi; akun laptop dan VPS pengguna tidak disentuh saat pengembangan.

Perbaikan bridge mencakup endpoint OAuth Go, status authorized, daftar koneksi API lengkap, session device privat, dan callback beberapa metode login. Arsip installer mempertahankan byte logo PNG.

Pemeriksaan menggunakan binary gateway nyata dan kredensial fixture, bukan akun atau kuota provider pengguna. Gateway Windows tersedia sebagai binary mandiri; wizard Agen Mini Windows masih memakai endpoint gateway yang sudah berjalan. CLI harness asli belum diganti SDK. Hasil CI dan batas pengujian tersedia dalam VALIDATION.md.

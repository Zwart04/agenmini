# Agen Mini 0.6.0

Tampilan dirombak berdasarkan ruang lega OpenAI/Apple dan hierarki mode gelap Linear. Chat, login, koneksi, formulir, dialog dan workspace memakai sistem visual yang konsisten, dengan font sistem dan aset lokal.

- Empat menu; tab memisahkan proyek, aktivitas, tim, jadwal, ide/biaya, akun layanan, MCP, skill, ingatan, update dan diagnostik. Draft dan posisi baca dipertahankan.
- Studio desktop dengan bentuk karakter beragam. Mobile memakai susunan ringkas tanpa furniture kecil; antrean/rapat memiliki slot terpisah yang tidak bertumpuk.
- Gerak memiliki pilihan Ikuti perangkat/Aktif/Mati; pilihan Aktif menghidupkan animasi karakter, sementara default mengikuti reduced-motion perangkat.
- Pengaturan lanjutan bisa dibuka melalui disclosure native; keyboard tabs/drawer, fokus, ukuran kontrol dan tema diperiksa.
- Backend, aturan izin, provider, model dan data pengguna tidak diubah untuk redesign ini. Update normal mempertahankan data dan konfigurasi.

Validasi lokal: 30 tes frontend/kontrol/catatan, ditambah pengujian layout yang memeriksa benturan 2/10/30 agen; 84 kombinasi tab/ukuran browser tanpa overflow pada 320/390/430/1024/1280/1440px. Tema, draft lintas tab, keyboard, drawer, dialog dan karakter diperiksa di preview backend terisolasi. Ini bukan pengujian model/provider atau deployment VPS pengguna.

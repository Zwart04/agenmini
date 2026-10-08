# Peta project Agen Mini

Folder utama di komputer ini: `C:\Users\Zwart\Downloads\Coding AI\agenmini`.
Kode, dokumentasi, alat revisi, model lokal dan hasil benchmark proyek ini
dikumpulkan di folder tersebut. Tidak perlu membuat salinan folder proyek baru.

Hasil web buatan model: `.local-tools/hasil-uji-web/`. Setiap percobaan mempunyai
folder sendiri agar sumber dan kegagalannya dapat ditelusuri. Folder percobaan
belum tentu berisi aplikasi selesai; periksa `results.json` dan laporan
`docs/LOCAL-APPS-EVAL.md` sebelum menganggapnya hasil yang sudah lulus.

| Folder/berkas | Isi |
| --- | --- |
| app/ | Backend Python: agen, harness, ingatan, skill, Telegram dan API |
| frontend/ | Tampilan ringan HTML/CSS/JS, provider dan maskot |
| gateway/ | Koneksi provider Go, OAuth dan API |
| tests/ | Tes regresi yang tetap dipakai setiap revisi; bukan sampah |
| scripts/ | Evaluasi model nyata dan pemeriksaan rahasia |
| docs/ | Panduan, atribusi, screenshot dan hasil pengujian |
| training/ | Persiapan dataset privat opsional; bukan pelatihan otomatis |
| windows/ | Packaging dan tes installer Windows |
| .github/ | Pemeriksaan Linux/Windows, runtime dan publikasi |
| agen*, installer-*, build_*.py | Perintah layanan dan packaging; letak dipertahankan agar update kompatibel |
| .local-tools/ | Alat pengembangan/model yang diunduh; lokal, diabaikan Git, tidak ikut installer |
| .local-tools/branding-original/ | Aset maskot asli, dipindahkan dari Downloads dan diperiksa SHA256 |
| data/ atau DATA_DIR | Riwayat, akun, ingatan, skill, backup; privat, bukan kode |
| _rilis/ | Arsip lokal untuk rollback; privat, tidak ikut Git/Docker/installer |
| dist/ | Hasil build yang bisa dibuat ulang; diabaikan Git |

Tes dan alat evaluasi yang reusable dipertahankan. Folder .test-tmp*, .test-temp*,
cache Python, clone referensi dan paket lama yang tidak dipakai dibersihkan.
Jangan unggah data, .env atau .local-tools ke GitHub. Model 0.8B/1.2B untuk
revisi lokal disimpan di .local-tools; tidak diunduh lagi dan tidak ikut ZIP.

## Akses cepat di Windows

- Kode aplikasi: `app/`, `frontend/` dan `gateway/`.
- Hasil web buatan model: `.local-tools/hasil-uji-web/`.
- Catatan hasil uji: `docs/LOCAL-APPS-EVAL.md`.
- Maskot asli: `.local-tools/branding-original/agenmini_branding_first_mascot/`.
- Arsip lokal: `_rilis/`; panduan pemasangan: `CARA-PASANG-WINDOWS.txt` dan `CARA-PASANG-VPS.txt`.

Simpan pengerjaan berikutnya di folder proyek ini. Model, hasil benchmark,
konfigurasi privat dan alat lokal tetap diabaikan Git; tidak perlu membuat
salinan proyek baru di direktori lain.

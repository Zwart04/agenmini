# Validasi Agen Mini 0.6.0

## Perubahan

Redesign frontend dari HEAD terbaru e2a2f9f (versi 0.5.6). Tidak mengubah implementasi model, provider, sandbox, data atau izin pengguna.

## Pemeriksaan lokal

- 30 tes frontend syntax/asset paths, office layout, control API dan workspace records lulus di Windows Python 3.12. Tes office menggunakan stdin untuk Node supaya tidak melampaui batas command line Windows.
- Layout memeriksa batas layar dan benturan label/status untuk 2, 10, 30 agen pada 252/284/330/358/398/720/936/1104px, termasuk seluruh agen menunggu atau rapat.
- Browser dengan backend preview terisolasi: 14 tab pada 320/390/430/1024/1280/1440px (84 pemeriksaan), tepat satu panel terlihat dan tidak ada overflow halaman.
- Tema terang/gelap, chat, kantor, akun layanan, MCP, settings, draft proyek lintas tab, keyboard ArrowRight, drawer serta dialog ditinjau. Tidak ada error JavaScript pada console.
- Animasi diuji di browser: Aktif menghasilkan transform karakter yang berubah; Ikuti perangkat/Mati berhenti pada perangkat dengan reduced-motion.
- CSS memakai font sistem/aset lokal dan animasi yang sudah ada; tidak menambah runtime frontend, layanan, request per karakter atau dependency produksi.

## Batas

Preview tidak menjalankan model, pekerjaan bot atau layanan provider pengguna. Status model yang tidak tersambung tetap ditampilkan apa adanya. Tidak mengklaim deployment atau validasi OAuth/Telegram/VPS pengguna. Workflow Linux dan Windows memeriksa commit sebelum publication release; ZIP diverifikasi dengan CRC dan SHA256 oleh build_release.py.

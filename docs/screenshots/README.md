# Galeri Agen Mini

Tangkapan langsung aplikasi versi 0.11.0, diperbarui 27 Oktober 2026.
Klik nama gambar untuk membuka berkas ukuran penuh. Desktop **2880 × 1920**;
mobile **780 × 1688**, diambil pada skala layar **2×** dengan PNG lossless.
Detail editor dipotong langsung dari panel yang sama, tanpa diperbesar.

Percakapan dan berkas memakai **data demo dokumentasi**, bukan hasil model.
Gateway tidak berisi akun atau API key. Tidak ada pengiriman ke Telegram,
panggilan model, atau akses VPS selama pengambilan gambar.

| Tampilan | Desktop | Mobile / alternatif |
| --- | --- | --- |
| Chat | [PNG](chat-desktop.png) | [Mobile](chat-mobile.png) |
| Panel kerja | [PNG](workbench-desktop.png) | [Mobile](workbench-mobile.png) · [Tema terang](workbench-light.png) |
| Editor lebih dekat | [Detail PNG](editor-detail.png) | Potongan panel asli |
| Workspace tim | [PNG](workspace-desktop.png) | [Mobile](workspace-mobile.png) · [Tema terang](workspace-light.png) |
| Katalog provider | [PNG](providers-desktop.png) | [Mobile](providers-mobile.png) |
| Harness dan self-improve | [PNG](harness-desktop.png) | [Mobile](harness-mobile.png) |
| Pilihan model lokal | [PNG](runtime-desktop.png) | [Mobile](runtime-mobile.png) |
| Notifikasi custom | [PNG](toast-desktop.png) | [Mobile](toast-mobile.png) |
| Dialog custom | [PNG](dialog-desktop.png) | Contoh dialog, tanpa menjalankan perubahan |
| Tema maskot | [Gelap](mascot-dark.png) | [Terang](mascot-light.png) |

[GIF 1440 × 960](preview.gif) · [MP4 1920 × 1280](preview.mp4)

Animasi adalah tur visual lima tangkapan antarmuka, masing-masing 3,2 detik.
MP4 memakai H.264, CRF 15 dan fast-start. GIF menyediakan preview langsung di
README; MP4/PNG mempertahankan detail lebih baik daripada palet GIF.
Website memakai WebP **lossless**, diperiksa identik piksel dengan PNG sumber,
serta gambar khusus mobile agar teks tetap terbaca.

## Mengambil ulang

Tool hanya untuk dokumentasi: Python dengan dependensi aplikasi, Playwright
Chromium, Pillow, dan ffmpeg berencoder H.264. Tidak menjadi dependensi baru
aplikasi. Jalankan dari root repo:

```sh
python scripts/media/serve.py --gateway /path/agenmini-gateway
# Terminal terpisah, dengan Playwright tersedia:
node scripts/media/capture.cjs
python scripts/media/export.py --ffmpeg /path/ffmpeg
```

Jika Playwright disediakan di lokasi lain, atur `AGENMINI_PLAYWRIGHT_MODULE`.
Server hanya memakai loopback, direktori temporer di `.local-tools`, dan sandi
acak privat. Ctrl+C menghentikan gateway miliknya serta menghapus data demo.
`capture.json` mencatat ukuran dan pemeriksaan browser, tanpa rahasia.

Berkas showcase lama yang terkompresi/dinamai salah digantikan oleh galeri ini.
`model-editor-v208.png` tetap merupakan bukti historis benchmark 23 Oktober;
tidak digambar ulang atau diganti dengan data demo. [Konteks dan batas uji](../LOCAL-APPS-EVAL.md).

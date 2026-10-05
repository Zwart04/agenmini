# Frontend Agen Mini

**Semua tampilan web berada dalam folder ini.** Mulai dari `index.html`, `theme.css` dan `layout.css` untuk mengubah desain. Tidak perlu Node build, React, bundler, font CDN atau framework. Backend Python tetap terpisah di `app/`.

## Peta berkas

| Berkas | Fungsi |
| --- | --- |
| `index.html` | Markup login, empat menu, halaman, formulir dan dialog |
| `theme.css` | Warna/variabel tema terang dan gelap |
| `base.css` | Tata letak dasar, sidebar, chat, formulir dan kontrol |
| `control.css` | Panel koneksi, model, setup dan komponen admin |
| `office.css` | Karakter, aksesori, ruangan, bubble dan animasi kantor |
| `layout.css` | Sistem desain akhir, hierarki tab, kartu, chat, studio, responsivitas dan dialog |
| `app.js` | State, helper API, ikon, chat, formulir bot/skill/ingatan/jadwal/pengaturan |
| `ui-state.js` | Menjaga draft, fokus dan scroll saat data diperbarui |
| `office.js` | Posisi karakter, ruangan, presence dan bubble aktual |
| `office-learning.js` | Diskusi, pelajaran dan pemakaian token/biaya |
| `social.js` | Formulir koneksi akun sosial |
| `control.js` | Koneksi AI/MCP, alat admin, aktivitas dan dialog rincian |
| `activity.js` | Aktivitas alat dan indikator pekerjaan |
| `workspace.js` | Proyek, izin, CRUD catatan, Smart Router dan akun host |
| `navigation.js` | Menata panel/tab dalam empat halaman tanpa mengganti draft, lalu memulai aplikasi |
| `dots/` | Aset karakter SVG lokal |
| `router.css`, `router-icons.js`, `router-bridge.js` | Penyesuaian visual/tautan dashboard 9router yang diproksi |
| `free-dashboard.js` | Penanda sesi dashboard FreeLLMAPI; bukan JWT/kredensial provider |
| `DESIGN.md` | Pedoman desain, aksesibilitas dan animasi ringan |

CSS dimuat berurutan: **theme → base → control → office → layout**. Aturan terakhir mengatur penyelarasan akhir. Script dimuat berurutan sesuai `index.html`; `app.js` harus lebih dahulu dan `navigation.js` harus terakhir. Script memakai global bersama, sehingga jangan menambahkan `async`, `defer`, atau `type="module"` tanpa memigrasikan seluruh dependensinya.

## Bagian halaman

`v-chat`, `v-office`, `v-ai`, `v-settings` adalah empat halaman utama: **Chat, Workspace, Koneksi, Pengaturan**. Markup bagian `v-bots`, `v-jobs`, `v-mcp`, `v-skills`, `v-memory`, `v-updates`, `v-models` dipindahkan ke halaman induk oleh `navigation.js` saat startup. Satu panel terlihat pada tiap halaman; fitur lainnya tetap dapat dibuka dari tab. Pagination/dialog dipakai untuk catatan panjang. Pengaturan lanjutan memakai details/summary native.

Untuk mengganti desain, ubah markup/CSS serta template komponen di JavaScript bila diperlukan. Pertahankan ID, `data-*`, nama formulir, event handler dan kontrak `/api/*` yang digunakan script. Ubah teks secara konsisten; jangan mengubah status gagal menjadi berhasil atau menambahkan progres palsu.

Backend melayani folder ini sebagai `/static/`; URL tersebut dipertahankan untuk kompatibilitas. Halaman `/` memerlukan backend untuk login, API dan SSE. Membuka `index.html` dengan `file://` atau server statis saja tidak menjalankan Agen Mini.

## Instruksi yang bisa diberikan kepada AI lain

> Perbaiki desain Agen Mini dalam folder `frontend/`. Baca `README.md` dan `DESIGN.md` di folder tersebut. Pertahankan empat menu, navigasi tab, kantor, semua fitur, ID/data-attribute yang digunakan JavaScript, endpoint API, urutan script dan perilaku draft/scroll. Gunakan CSS ringan dan aset lokal; jangan menambah framework atau dependensi berat. Periksa tema terang/gelap, desktop 1024/1280/1440 dan mobile 320/390/430. Jangan mengubah backend, data pengguna atau aturan izin demi perubahan visual.

Ini panduan desain umum, bukan daftar repo/akun pribadi.

## Menjalankan dan memeriksa

Dari akar repo, gunakan pemasang atau Docker Compose yang dijelaskan di README utama. Browser mengakses aplikasi melalui backend, sehingga API/login/SSE tetap bekerja. Untuk perubahan frontend pada Docker, build ulang image aplikasi; memasang ulang provider/model tidak diperlukan.

```bash
python -m pytest tests/test_frontend_syntax.py tests/test_office_layout.py -q
```

Tes sintaks memerlukan Node. Selain tes otomatis, periksa halaman nyata dengan browser: semua menu, scroll, dialog, formulir, tombol, unduhan, karakter, tema dan ukuran layar. Pastikan teks berada di dalam kartu melengkung, kontrol terlihat sebagai tombol, tidak ada overflow horizontal, dan polling tidak menimpa formulir yang sedang diisi.

Docker, pemasang VPS, Windows installer dan ZIP source mengambil frontend dari folder yang sama. Jangan menyimpan API key, cookie, `.env`, data, hasil pengguna atau log privat di sini.

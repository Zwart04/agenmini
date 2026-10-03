Semua frontend dipisahkan ke folder `frontend/`: HTML, tema, CSS, JavaScript, SVG dan penyesuaian dashboard. CSS dan script utama dikeluarkan dari HTML, dengan urutan eksekusi yang sama. Panduan frontend memetakan berkas dan menyediakan instruksi untuk desainer/AI lain.

Docker, VPS dan Windows installer menggunakan folder frontend yang sama. URL `/static/` tetap kompatibel. Update VPS mencadangkan kode dan memindahkan folder UI lama ke backup privat; data/config tidak dihapus.

Diuji melalui regresi Linux, browser pada pemasangan nyata, serta CI pemasangan Windows. Model/provider tetap mengikuti kredensial dan kuota masing-masing.

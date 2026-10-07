# Agen Mini 0.10.0

Harness bawaan mengadaptasi inti kontrol DeepSeek ke Python: tindakan alat berurutan, identitas call/result, journal privat, deadline dan penanganan tindakan terputus tanpa replay otomatis. Mode Kosong tetap terpisah; runtime DeepSeek asli tetap pilihan eksternal yang dipasang saat dipilih. Atribusi MIT dan commit sumber disertakan dalam paket.

Panggilan alat tidak lagi terpotong diam-diam pada tiga panggilan pertama. Batch dibatasi delapan secara eksplisit; tindakan yang ditunda tercatat parsial sampai benar-benar dijalankan. Jalur edit proyek Windows dinormalisasi agar folder tidak terduplikasi; editor JS membaca HTML aktual.

Chat mendapat Panel kerja dengan editor ringan, perubahan sebelum/sesudah, draf kode langsung, preview offline terisolasi, Browser dan log. Editor menolak konflik dengan perubahan agen dan membuat salinan sebelum menyimpan. Preview memakai browser pengguna; panel Browser bukan mesin otomatisasi agen. Import module, backend dan situs yang menolak iframe memerlukan server/tab tersendiri. Model dan akses alat dapat dipilih pada chat.

Maskot dari aset pengguna dibersihkan menjadi PNG transparan dan dianimasikan melalui CSS saat bekerja. Panel diperiksa pada desktop dan mobile 390 px, dengan kontrol custom, fokus modal dan dukungan reduced motion. Tidak menambah Monaco, Node service atau server animasi.

Pemasang memperbaiki 404 pada rilis 0.9.0: placeholder versi URL gateway diganti saat packaging; binary dan SHA256 diunduh ke staging sebelum mengganti binary lama. Instalasi di atas versi lama mempertahankan data/model/akun. README serta panduan pasang, update dan remove ditulis ulang.

Uji model lokal CPU 0.8B/1.2B memakai tugas converter gambar dan editor teks, bukan landing page atau template hasil. Ditemukan keluaran terpotong, sintaks salah dan kontrak HTML/JS salah. Guard membatasi perbaikan, memvalidasi tiap berkas, dan menolak menyimpan proyek yang belum valid. Detail hasil serta batas kualitas model ada di VALIDATION.md. Tidak ada klaim training bobot atau kemampuan setara model besar.

Publikasi mensyaratkan GitHub Actions Linux, installer Windows nyata dan matriks CLI upstream pada commit yang sama. Pengujian tidak mengakses VPS atau akun provider pengguna.

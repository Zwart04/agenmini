# Agen Mini 0.7.0

Setup baru dapat memilih Kosong atau Paket bawaan. Kosong tetap berisi satu agen tanpa skill, ingatan, MCP dan tim bawaan sesudah restart/update; harness minimal dan pembelajaran mati. Akses penuh dipilih secara terpisah. Data instalasi lama dipertahankan.

- Kandidat prosedur terhubung ke bukti alat, dapat ditinjau/diedit sebelum diaktifkan, serta punya riwayat revisi dan rollback. Sapaan, galat, cache dan koreksi tidak dianggap keberhasilan.
- Refleksi model tidak mengaktifkan skill sendiri. Penilaian ulang tidak menambah skor palsu; koreksi menarik bukti lama tanpa menimpa edit manual.
- Telegram menawarkan simpan prosedur hanya saat ada bukti, ditambah /belajar untuk melihat kandidat percakapan sendiri. Jawaban tugas tetap berasal dari model dan hasil alat.
- Daftar alat lokal disingkat, dengan find_tools untuk membuka definisi sesuai tugas tanpa memperluas izin. Eksekusi kode Windows memperbaiki kutip shell dan batas RAM grafik.
- Koneksi menjadi Otomatis, Model lokal dan AI terhubung. API langsung/gateway OAuth berada di satu pintu; koneksi lama dipertahankan, layanan tambahan tetap opsional.
- Ekspor privat jawaban yang dinilai Sesuai, validator/deduplikasi/split dataset dan panduan training LoRA/QLoRA tersedia. Tidak melatih bobot di VPS atau menjanjikan kualitas frontier.

Pemeriksaan dilakukan pada preview terisolasi, uji kontrak Telegram tanpa pengiriman langsung, eksekusi berkas/kode nyata dan CI Linux/Windows sebelum publication. Model/provider, OAuth, akun Telegram dan VPS pengguna belum diuji langsung; seluruh klaim dibatasi sesuai VALIDATION.md.

Dropdown, saran model, konfirmasi, input singkat dan notifikasi memakai komponen custom sesuai tema, dengan keyboard/Escape/fokus. Tidak memakai alert/confirm/prompt browser atau library UI tambahan.

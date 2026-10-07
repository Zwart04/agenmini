# Menghapus Agen Mini

## Linux / VPS

`agen hapus --dry-run` menampilkan rencana tanpa mengubah layanan.

`agen hapus` meminta Anda mengetik HAPUS, menghentikan supervisor dan container
project Agen Mini, lalu menghapus shortcut/units. Data, `.env`, cache model dan
volume provider dipertahankan agar bisa dipasang kembali.

`agen hapus --all` juga menghapus seluruh data/model/kredensial Agen Mini dan
folder `/opt/agenmini`. Buat backup privat sebelum memakai opsi ini. Ini bukan
cara memperbarui aplikasi. Docker dan container project lain tidak dicopot.

## Windows

Buka Settings → Apps → Installed apps → Agen Mini → Uninstall. Uninstaller
menghentikan server Agen Mini dan menghapus aplikasi/shortcut. Data berada
terpisah di `%LOCALAPPDATA%\AgenMini\data` dan tetap disimpan.

Jika ingin menghapus data permanen, backup dahulu, pastikan aplikasi telah
berhenti, lalu hapus folder data tersebut secara manual. Jangan menghapus
folder data saat update. Memasang installer versi lama mengganti kode; tidak
otomatis mengembalikan skema database atau isi backup.

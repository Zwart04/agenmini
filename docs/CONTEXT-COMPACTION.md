# Konteks panjang dan pemulihan harness

Web dan Telegram memakai jalur `agent.Turn` yang sama. Pada harness Agen Mini,
riwayat untuk model dirapikan ketika perkiraan ukuran permintaan melebihi
anggaran konteks. Mode kosong (`none`) tidak memakai pemadatan ini.

1. Cadangkan ruang jawaban dan daftar alat. Untuk llama-server lokal, baca
   kapasitas slot dari `/props`; hasilnya disimpan selama 60 detik. Jika server
   tidak menyediakan metadata valid, gunakan 4.096 sebagai batas cadangan.
   Untuk API lain, gunakan pengaturan `num_ctx`.
2. Pendekkan kutipan hasil alat yang panjang, dengan bagian awal dan akhir
   tetap tersedia. Jangan memotong argumen panggilan atau permintaan terbaru.
3. Jika masih terlalu besar, gantikan putaran lama dengan catatan kerja
   ekstraktif. Panggilan alat dan hasilnya tetap berpasangan.
4. Jika provider menolak karena konteks terlalu panjang, kecilkan permintaan
   dan coba paling banyak dua kali lagi. Galat autentikasi dan respons yang
   sudah mengirim teks tidak diulang lewat jalur ini.
5. Hentikan panggilan alat identik yang ketiga. Penulisan yang berhasil dapat
   membuka kembali pemeriksaan berkas yang sama; mutasi gagal tidak menghapus
   pembatas pengulangan.

Catatan lintas giliran menyimpan batas ID pesan dan kutipan tujuan, permintaan
terbaru, serta bukti alat. Catatan ini bisa dibuka di atas riwayat chat.
Pesan pengguna/asisten di SQLite tidak dihapus oleh pemadatan. Catatan bukan
bukti bahwa tugas sudah selesai, dan tidak melatih ulang bobot model.

## Batas yang perlu diketahui

- Ukuran token adalah perkiraan UTF-8 konservatif, bukan tokenizer setiap
  provider. Kapasitas seluruh model API belum ditemukan secara otomatis.
- Catatan ekstraktif dapat melewatkan rincian lama. Baca kembali riwayat dan
  berkas sumber sebelum mengambil tindakan yang bergantung pada rincian itu.
- Trace alat yang disimpan sudah dibatasi ukurannya. Ini bukan arsip lengkap
  semua keluaran alat; klaim penyimpanan riwayat berlaku pada pesan chat.
- Pemadatan tidak menjamin model kecil mampu menyelesaikan tugas kompleks.
  Kode hasil model harus tetap melewati pemeriksaan perilaku dan browser.
- Pengujian dengan model tiruan memverifikasi mekanisme pemulihan, bukan
  kecerdasan model atau mutu hasil aplikasi.

## Referensi implementasi

Implementasi Python ini memakai gagasan arsitektur dari sumber berikut,
tanpa memasang runtime mereka ke dalam Agen Mini:

| Proyek | Revisi yang diperiksa | Bagian yang dipelajari |
| --- | --- | --- |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/687f282e8625c6b8d11ff58211a90524be2e4317) | `687f282e` | Pemendekan hasil alat sebelum ringkasan, pasangan alat, pemulihan overflow |
| [oh-my-pi](https://github.com/can1357/oh-my-pi/tree/2220e58146ebe31508e7a216242840d373e082d0) | `2220e581` | Anggaran konteks kecil dan penghentian pengulangan tanpa kemajuan |
| [OpenCode](https://github.com/anomalyco/opencode/tree/81b2d7a1b936083a8e16ed7bc740523baebb250e) | `81b2d7a1` | Catatan kelanjutan tugas dan pengecilan konteks setelah penolakan |

[REA](https://github.com/morluto/rea) 6.7.0 juga dipakai untuk analisis statis
artefak npm resmi `@deepseek-ai/dsh-compaction-basic@0.0.1-rc.3`.
Analisis `lib/index.js` berhasil diparse dan menghasilkan evidence ID
`ev_df5ee20d338354c34108b1176818643554e934e6fbd96632a6ac483a3d4b33c6`.
Analisis AST ini bukan bukti eksekusi runtime. REA adalah alat pengembangan;
pengguna Agen Mini tidak perlu memasangnya.

# Uji aplikasi dengan model lokal kecil

Pengujian pada Windows, 7 Oktober 2026, memakai llama.cpp CPU b11443,
4 thread, konteks 8192 dan satu slot per model. Data uji terpisah;
hasil kode berasal dari model, tidak diganti dengan template evaluator.
Tugas: converter gambar offline dan editor teks UTF-8 dengan replace-all.
Prompt memuat penanda acak agar hasil dan percakapan dapat dicocokkan.

| Model / putaran pengembangan | Converter | Editor teks |
| --- | --- | --- |
| Qwen3.5 0.8B Q4_K_M, awal | Gagal: penjelasan masuk JavaScript | Gagal: HTML terpotong |
| Qwen3.5 0.8B, perbaikan berkas | Gagal: CSS terpotong | Gagal: deklarasi JavaScript berulang |
| Qwen3.5 0.8B, konteks diperkecil | Artefak lolos sintaks/ZIP; gagal perilaku browser | Uji terpisah, tidak dianggap lulus berdasarkan converter |
| LFM2.5 1.2B Instruct QAD Q4_0 | Gagal kontrak antarberkas | Artefak lolos sintaks/ZIP; gagal perilaku browser |
| LFM2.5 1.2B, guard HTML/kontrol | Gagal, tidak ada ZIP hasil | Gagal, tidak ada ZIP hasil |
| Qwen3.5 0.8B, guard final (`2d2a07d7`) | Gagal: README terpotong; tidak ada ZIP hasil | Gagal: kontrol yang diminta belum lengkap |
| LFM2.5 1.2B, pemulihan fence (`b03d9b71`) | Artefak lolos struktur; gagal unggah PNG valid di browser | Gagal: kontrol yang diminta belum lengkap |

Browser nyata mengunggah PNG valid 32×16 ke converter Qwen (`a2ed35ac`).
Aplikasi menampilkan “File tidak valid” dan menonaktifkan tombol konversi.
Kode juga menyalin file asli, tanpa proses canvas/resize yang diminta.
Ini **gagal**, meskipun pemeriksaan sintaks dan ZIP sebelumnya berhasil.

Browser nyata mengunggah teks “apel apel jeruk café 日本語” ke editor LFM
(`cc96a2e3`) lalu menekan Save. Console mengembalikan
`TypeError: file.readAsText is not a function`. Replace-all, kontrol pencarian
dan hitungan kata yang diminta belum lengkap. Ini **gagal**.

Uji converter LFM setelah pemulihan fence mengunggah PNG valid 32×16 lalu
menekan Convert. Aplikasi menampilkan “File must be a JPEG, PNG or WebP”
karena membandingkan ekstensi terhadap MIME. Ini gagal. Uji perbaikan memakai
agent.Turn juga menemukan jalur Windows diprefiks dua kali; bug aplikasi
tersebut diperbaiki dan diberi tes regresi, bukan dianggap kesalahan model.

Temuan tersebut menghasilkan guard per berkas, pemeriksaan kontrol yang
diminta, penolakan HTML yang bercampur modul lain, pemulihan wrapper fence
yang hanya mengambil berkas yang diminta, serta perbaikan JS per berkas.
Kode yang terpotong atau tetap invalid tidak disimpan sebagai proyek selesai.
Metadata `behavior_verified:false` membedakan artefak/sintaks dari perilaku.
Guard integritas bukan jaminan seluruh fitur yang dihasilkan model bekerja.

SHA256 bobot yang benar-benar dijalankan:

- Qwen: `fb044e93939a70469c905781334f5de1e6c8b608ced6cbc8c9249bd4127d9526`
- LFM: `bb741ebb106d543e9de114b843a3d3d73d51c74b5801e69da2abde821a0cb3e1`

Bobot berasal dari repository Bartowski Qwen3.5 0.8B dan LiquidAI LFM2.5
1.2B GGUF. Bukan model API yang diam-diam menggantikan inferensi lokal.
Kanal `tg` menjalankan alur `agent.Turn` bersama, bukan koneksi Telegram nyata.
Browser/test evaluator tidak ditambahkan sebagai dependensi VPS.

Ulangi dengan model sendiri:

```bash
python scripts/evaluate_apps.py --server-exe /path/llama-server --gguf /path/model.gguf --model-label "Nama dan quant model"
```

Laporan, draft dan kode tetap dalam direktori temp yang dicetak evaluator;
gunakan `--output-dir` dengan direktori baru untuk menyimpannya bagi review.
Uji browser independen tetap diperlukan. Model 0.8B/1.2B belum terbukti andal
untuk kedua tugas ini; jangan menyamakan harness dengan training bobot atau
kemampuan model besar.

Perbaikan melalui agen nyata menemukan jalur Windows yang menggandakan folder
proyek; normalisasi jalur diperbaiki dan diuji regresi. Percobaan berikutnya
berhasil menulis berkas yang tepat, tetapi LFM tetap menghasilkan logika
converter yang keliru dan respons JSON akhir invalid. Status tugas gagal,
bukan bukti aplikasi bekerja. Permintaan asli pemilik kini disertakan dalam
editor alat agar ringkasan model tidak menghilangkan kriteria fungsi.

## Benchmark video editor, 7 Oktober 2026

Tugas berikutnya adalah video editor offline terinspirasi layout CapCut:
import MP4/WebM, playback/seek, trim, overlay teks, dan export WebM baru
melalui canvas/MediaRecorder. Export tanpa audio dibolehkan dan harus
dijelaskan. Ini uji aplikasi fungsional, bukan klaim menyalin seluruh CapCut.
Prompt Inggris yang dapat diulang ada di `scripts/benchmarks/video-editor.txt`.
Putaran awal menggunakan instruksi Indonesia yang tersimpan dalam laporan.

Qwen 0.8B gagal setelah perbaikan: berulang kali mendeklarasikan ID kontrol.
LFM 1.2B awal gagal dengan kontrol hilang/ID ganda. Setelah rencana interface
dipisahkan dari logika, model menghasilkan lima berkas, tetapi verifikasi
Unicode Windows gagal karena pembacaan memakai encoding bawaan, bukan UTF-8.
Keluaran model disalin persis ke direktori review privat untuk uji browser,
tanpa mengganti kode dengan template atau perbaikan evaluator.

Browser mengunggah MP4 fixture sintetis 320×180, 24 fps, 5 detik, lalu mencoba
play dan export. Hasil **gagal**: `module is not defined`, deklarasi `media`
berulang, dan preview berupa div tanpa elemen video. Tidak ada video ekspor
yang sah. Layout 390px tidak melebar horizontal, tetapi desain belum memenuhi
brief CapCut. Screenshot desktop/mobile dan console disimpan bersama laporan
lokal. Kemampuan model kecil belum boleh dianggap andal untuk tugas ini.

Temuan memperbaiki harness: CSS menerima HTML/kelas dan arah desain nyata;
HTML dibuat sebelum CSS/JS; JS menerima modul terdahulu; rencana memisahkan
interface dari algoritme; jenis kontrol eksplisit dan ID ganda diperiksa;
script browser diperiksa bersama untuk benturan scope dan CommonJS;
pembacaan verifikasi memakai UTF-8. Frasa “not a landing page” kini diarahkan
ke proyek fungsional. Percobaan yang terlanjur masuk pembuat landing page
dihentikan dan dikecualikan dari benchmark aplikasi.

```bash
python scripts/evaluate_apps.py --server-exe /path/llama-server --gguf /path/model.gguf --case video --prompt-file scripts/benchmarks/video-editor.txt --output-dir /path/new-private-review
```

Evaluator menjalankan inferensi model nyata dan mencatat kegagalan apa adanya.
Guard struktur/sintaks bukan ukuran kualitas visual atau bukti fitur bekerja.
Perbaikan ini tidak menambah proses model, browser, atau framework di VPS.

Putaran akhir LFM dengan prompt Inggris dan tipe kontrol eksplisit tetap
gagal setelah satu perbaikan: `startInput` hilang dan `titleInput` berubah
menjadi div. Putaran itu dihentikan oleh guard sebelum menjadi ZIP hasil.
Status akhir benchmark video editor: **belum lulus**. Keluaran sebelumnya
juga belum layak sebagai aplikasi video editor; tidak ada demo sukses yang
ditambahkan untuk menutupi kegagalan model.

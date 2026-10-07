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

Eksperimen selanjutnya memecah kode menjadi panel dan fungsi kecil. Jalur
ini netral provider: lokal, API online, dan router memakai generator yang sama.
Resep berisi instruksi desain/kontrak fungsi, bukan sumber HTML/CSS/JS siap pakai.
Setiap bagian sumber yang valid disimpan bersama hash dan identitas model.
Namun LFM 1.2B dan Qwen 0.8B masih gagal memenuhi kontrak HTML, bahkan sebelum
uji ekspor. Karena itu jalur bagian sumber **belum diaktifkan sebagai default**.
Aktifkan hanya pada evaluator privat dengan `--source-parts`. Eksperimen Qwen
dapat memakai `--thinking-budget 256`, dibatasi maksimum 512; ini bukan janji
peningkatan kualitas. Jalur utama pembuatan proyek tetap tersedia untuk semua
backend. Tidak ada template runtime yang disisipkan untuk meluluskan benchmark.

Putaran lanjutan membandingkan Qwen 0.8B Q4 dan Q8 memakai parameter non-thinking
resmi; keduanya tetap gagal kontrak dokumen. Mengubah kuantisasi belum terbukti
menyelesaikan tugas. Qwen2.5-Coder 0.49B Q5 dipakai sebagai pembanding coding
yang lebih kecil, bukan bukti bahwa benchmark model 1B telah lulus. Model ini
berhasil menulis bagian HTML dan CSS dengan instruksi desain terstruktur,
tetapi putaran awal masih gagal pada fungsi trim/timeline.

Guard kini memeriksa sintaks CSS, kelengkapan referensi DOM, batas media-query
mobile dan field state bersama. Konteks JS membawa kontrak deklarasi/fungsi,
bukan semua implementasi sebelumnya yang mudah disalin model kecil. Percobaan
perbaikan menerima kontrak yang sama. Cache bagian memverifikasi hash task,
source mentah dan source terpilih; evaluator menuntut GGUF yang identik saat
melanjutkan. Respons mentah tetap disimpan agar pemilihan elemen/penyusunan
hasil dapat diaudit. Ini generasi yang dibimbing instruksi, bukan training bobot
model atau bukti kemampuan umum setara model besar.

Instruksi desain memuat spesifikasi selector/properti; sumber HTML/CSS/JS tetap
ditulis model. Tidak ada aplikasi siap pakai yang dijadikan fallback. Pengujian
jalur generator mencakup backend lokal, online dan router; test tersebut memakai
stub dan tidak mengklaim semua model online telah diuji secara nyata. Pemeriksaan
sintaks dan struktur tidak menggantikan pengujian ekspor video di browser.

Putaran pembanding 0.49B berikutnya menghasilkan ZIP yang lolos struktur/sintaks.
Uji browser nyata tetap **gagal**: pemilih file menerima fixture MP4, tetapi
preview tetap tidak mempunyai source dan tombol Play tidak aktif. Kode init
berisi pengganti helper dengan komentar simulasi dan tidak memanggil startup.
Tampilan desktop dan 390px juga belum layak. Bukti screenshot berada dalam
laporan privat `video-coder05-parts-v13`; tidak dipublikasikan sebagai demo sukses.
Guard kini menolak redefinisi helper pada bagian fungsi, placeholder/simulasi,
startup yang hilang, serta kontrak API impor/playback yang tidak ditulis.
Pemeriksaan ini tetap bukan bukti lengkap perilaku; uji browser wajib diulang.

Pembanding lanjutan: DeepSeek Coder **1.3B** Q5_K_M CPU, bukan 1B tepat.
GGUF TheBloke revision `4595af8c3dff738094bd6c86054dfb5a90d5c41e` diverifikasi
SHA256 `d5dcc2a484498b412b8bf5821b0ef2a7ea2e1984b37d15e14344259068d19a31`.
GGUF lama tidak membawa metadata chat/pre-tokenizer; putaran awal mengulang
prompt. Evaluator menerima format percakapan resmi dari tokenizer DeepSeek
revision `e063262dac8366fc1f28a4da0ff3c50ea66259ca` dan override llama.cpp
`tokenizer.ggml.pre=str:deepseek-coder`, tanpa mengubah tensor bobot. Format
komunikasi ini tidak berisi sumber aplikasi. Hash format dan parameter inferensi
dicatat, dan resume menolak pengaturan yang berbeda. Hasil belum boleh dianggap
lulus hanya karena HTML mulai valid.

Parser respons kini memilih satu blok fenced sesuai bahasa berkas walaupun
model menulis pengantar; beberapa blok bahasa yang sama tetap ditolak sebagai
ambigu. CSS harus memakai selector ID/class yang sesuai kontrak. Tiga helper
(format waktu, status error/success, kontrol sibuk) diuji dalam fixture Node
terbatas melalui sandbox sebelum diterima. Fixture bukan kode aplikasi dan
tidak dikirim sebagai sumber hasil. Tes ini tidak menguji browser atau encoding
video; import/playback/export masih harus dibuktikan melalui browser nyata.

Tes integrasi harness juga menjalankan `Turn.run` untuk enam kombinasi:
lokal/online/router melalui web/Telegram. Model pada tes tersebut adalah stub;
alat menulis berkas nyata di direktori uji, hasilnya mengikuti respons stub
yang berbeda tiap kombinasi, dan jurnal call/result diperiksa. Ini membuktikan
jalur harness bersama, bukan kualitas semua provider atau koneksi Telegram
langsung. Pilihan model tidak mengganti proses pemeriksaan dan perbaikan.

Putaran DeepSeek 1.3B terkini tetap **gagal** pada kontrol sibuk: model berulang
kali menonaktifkan impor saat media belum dimuat, sehingga pengguna tidak bisa
memilih video pertama. Guard perilaku menolak sumber itu; tidak ada koreksi
kode aplikasi yang disisipkan evaluator untuk membuat benchmark terlihat lulus.

Perbaikan eksperimen sekarang dapat meminta patch teks kecil kepada model,
alih-alih selalu meminta seluruh fungsi ulang. Teks `find` harus ada tepat
sekali, format harus lengkap, dan keseluruhan patch harus mengubah sumber.
Patch yang ambigu, terpotong atau tidak mengubah hasil ditolak. Perubahan
diterapkan ke memori lalu diperiksa dengan kontrak/sintaks/tes perilaku yang
sama. Sumber awal, respons patch, hash tiap tahap dan modelnya dipertahankan;
cache memutar ulang rantai perubahan sebelum memakai hasil. Semua byte
pengganti berasal dari respons model, bukan kode buatan evaluator.

Putaran DeepSeek 1.3B dengan patch masih gagal pada kontrol sibuk: model
mengulang patch tanpa perubahan yang menyelesaikan galat. Log tetap gagal,
dan jalur eksperimental tetap tidak menjadi default. Evaluator juga mencatat
`checks/` per percobaan, termasuk galat nyata, hash source dan jenis helper
yang diuji. Lolos helper tetap tidak membuktikan impor/ekspor video di browser.

Pembanding berikutnya memakai GGUF resmi IBM `granite-4.0-1b`. Nama model
memuat "1b", tetapi tabel arsitektur resmi menyebut **1.6B parameter** untuk
versi dense tersebut. Hasilnya harus dilabeli pembanding 1.6B, bukan keberhasilan
model tepat 1B. Sumber: https://huggingface.co/ibm-granite/granite-4.0-1b.

Pada putaran Granite privat `video-granite16-parts-v3` sampai `v8`, model
berhasil memperbaiki atribut header dan satu selector monitor melalui patch
buatannya sendiri. Pemeriksaan kini menolak atribut style inline yang membuat
tombol/link tetap tersembunyi ketika status berubah, link download tanpa atribut
download, serta selector CSS yang tidak sesuai elemen. CSS dibagi per aturan
agar konteks lebih kecil; pembagian ini tetap berupa instruksi, tanpa kode
runtime yang diisi evaluator.

Namun Granite berulang kali menghasilkan selector `[hidden]:` tanpa blok CSS.
Putaran sampai `v8` **gagal** pada aturan visibilitas, sebelum JavaScript dan uji
browser. Kode dengan sintaks tidak lengkap sekarang diminta ulang sebagai
bagian lengkap; patch hanya dipakai untuk sumber yang sintaksnya valid.
Patch yang merusak sintaks dikembalikan ke sumber sebelumnya sebelum model
memperbaikinya lagi. Pada upaya patch terakhir, model dapat diminta menjelaskan
galat dulu; penjelasan beserta hash dicatat, tetapi tidak dipasang sebagai kode.
Diagnosis itu juga belum membuat benchmark video editor ini lulus.

Pada `v9`, instruksi atribut visibilitas diperjelas tanpa memberi kode jawaban.
Model berhasil menulis aturan lengkap pada percobaan kedua dan menyelesaikan
CSS desktop/mobile. Putaran tetap **gagal** di fungsi kontrol sibuk: tombol
pemutaran/ekspor dapat aktif sebelum video dimuat, lalu patch model justru
memotong fungsi. Guard menolak dan mengembalikan patch rusak. Belum ada bukti
impor, playback, trim atau ekspor hasil melalui browser untuk putaran ini.

Perbaikan berikutnya menambah format patch nomor baris. Model cukup menulis
nomor baris asli dan kode pengganti, tanpa menyalin teks pencarian panjang;
hingga delapan baris berbeda dapat diubah. Alamat mengacu pada sumber sebelum
patch, duplikat/nomor di luar sumber ditolak, dan penerapan tetap atomik.
Nomor kandidat dipersempit berdasarkan identifier yang disebut galat nyata;
jika ada galat struktur tanpa identifier yang dikenali, seluruh baris tetap
tersedia agar perbaikan bagian lain tidak terhalang. Format teks
pencarian lama masih dapat diputar ulang agar provenance cache tidak hilang.

Granite `v10` tetap menghasilkan patch tanpa perubahan, lalu `v11` menggeser
assignment ke baris yang salah dan menambah kasus gagal. Hasil tetap **gagal**.
Pemeriksaan helper sekarang mencatat kasus gagal satu per satu; patch yang
menambah kegagalan pada kasus sebelumnya lolos dikembalikan ke sumber lama.
Tes regresi memeriksa skenario patch memperbaiki playback tetapi merusak impor
video pertama, beserta pemutaran ulang hash patch dan routing semua backend.

Evaluator juga memiliki profil opt-in `--sampling-profile greedy` (temperature
nol). Uji CPU DeepSeek Coder 1.3B `video-deepseek13-parts-v14` dengan profil ini
masih **gagal** di atribut hidden tombol batal pada header. Pengaturan sampling,
patch dan instruksi ini tidak melatih atau mengubah bobot model.

Pembanding lebih kecil Qwen Coder 0.49B `video-coder05-parts-v17` juga **gagal**
di header: atribut hidden/download tidak lengkap dan patch model mengganti
tombol batal dengan tombol ekspor duplikat. Model juga menulis onclick yang
merujuk helper di luar fragment terpilih. Guard HTML kini menolak handler inline
agar event listener tetap berasal dari app.js yang lengkap dan diperiksa.
Ini masih belum menjadi keberhasilan benchmark model sekitar 1B.

Pemeriksaan routing mencakup model lokal/API online/router. Tes respons stub
tidak membuktikan mutu model online, dan putaran CPU nyata ini tidak membuktikan
model sekitar 1B dapat menghasilkan aplikasi setara CapCut. Jalur source-parts
tetap eksperimen opt-in; tidak diaktifkan sebagai default pengguna.

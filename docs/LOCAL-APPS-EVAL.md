# Uji aplikasi dengan model lokal kecil

Pengujian pada Windows, 7 Oktober 2026, memakai llama.cpp CPU b11443,
4 thread, konteks 8192 dan satu slot per model. Data uji terpisah;
hasil kode berasal dari model, tidak diganti dengan template evaluator.

Harness Agen Mini dipakai bersama oleh model lokal, API online dan router,
baik di web maupun Telegram. Model lokal kecil menjadi acuan uji yang sulit,
bukan satu-satunya model yang mendapat alur kerja tersebut. Harness membantu
melalui konteks, alat, pemeriksaan dan perbaikan berdasarkan kegagalan nyata;
tidak menjamin setiap model lemah akan menyamai model besar. Tes routing dengan
respons stub membuktikan jalur integrasi, bukan mutu jawaban provider nyata.
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

Uji Qwen 0.8B Q8 dengan penalaran dibatasi 256 token menemukan galat anggaran:
diagnosis memiliki batas keluaran 220 token, sehingga log llama.cpp menunjukkan
220 token terpakai tanpa teks jawaban. Panggilan diagnosis dan patch kini
menyediakan tambahan anggaran maksimum 512 token hanya ketika penalaran lokal
aktif; anggaran jawaban API online/router tidak diubah. Batas penalaran server,
jumlah percobaan serta batas waktu turn tetap berlaku.

Pada `video-qwen08q8-parts-thinking256-v2`, model benar-benar memperbaiki atribut
header menggunakan patch nomor baris. Uji berhenti pada panel media yang tidak
memiliki input unggah. Bagian dengan elemen/fungsi wajib yang hilang sekarang
diminta ulang secara lengkap, dan patch yang menghapus struktur wajib ditolak.
Namun putaran `v3` tetap **gagal**: model masih tidak menulis input file yang
diminta. Ini tidak dipublikasikan sebagai aplikasi atau demo sukses.

Putaran Qwen 0.8B Q8 `v4` menyelesaikan delapan bagian HTML setelah permintaan
ulang tidak lagi menyertakan sumber yang ditolak. Pada `v5`, model memperbaiki
font sistem dan selector header/footer. Guard font menolak nama keluarga
multi-kata yang tidak sengaja menggantikan font sistem. Semua kode pengganti
tetap berasal dari respons model; harness tidak menyisipkan implementasi.

Putaran `v6` gagal karena model memasukkan satu blok CSS lengkap ke patch satu
baris, sehingga blok terduplikasi. Patch yang merusak sintaks/struktur atau
kasus perilaku dikembalikan, lalu percobaan terakhir meminta bagian lengkap
baru. Permintaan patch sekarang memuat kontrak semantik tanpa instruksi format
raw source yang bertentangan dengan JSON patch. Baris selector yang gagal
ditentukan dari posisi parser CSS, bukan kode jawaban buatan evaluator.

Pada `v7`, model berhasil memperbaiki aturan judul, tetapi gagal di `.statusbar`.
`v8` dengan selector literal di konteks/system juga **gagal**: respons terakhir
menulis `.selector ".statusbar"` alih-alih selector yang diminta. Tidak ada
aplikasi lengkap atau bukti browser impor/playback/trim/ekspor untuk putaran
ini. Sebanyak **119 tes lokal** untuk jalur source-parts, proyek, inti harness
dan workflow lolos; ini tidak mengubah hasil benchmark model nyata tersebut.

Pemeriksaan routing mencakup model lokal/API online/router. Tes respons stub
tidak membuktikan mutu model online, dan putaran CPU nyata ini tidak membuktikan
model sekitar 1B dapat menghasilkan aplikasi setara CapCut. Jalur source-parts
tetap eksperimen opt-in; tidak diaktifkan sebagai default pengguna.

## Keluaran CSS terstruktur

Aturan CSS tunggal dapat diminta sebagai objek JSON dengan satu string
`source`. Pada llama.cpp, schema membatasi selector literal yang sudah ada di
kontrak dan bentuk satu blok kurung; properti/nilai tetap ditulis oleh model.
Pada API/router, format JSON diminta dan hasil tetap diperiksa setelah respons.
Schema tidak memuat deklarasi atau implementasi aplikasi. Aturan media tetap
memakai jalur sumber biasa.

Ini constrained decoding, bukan training bobot atau template aplikasi.
[Dokumentasi JSON Schema llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md#json-schemas--gbnf)
menjelaskan bahwa schema membatasi keluaran dan perlu dijelaskan juga di prompt.
Evaluator menyimpan JSON mentah, string sumber hasil decoding, format sumber,
hash dan patch model. Reuse memeriksa kembali string/patch persis tersebut;
JSON rusak atau berisi kunci tambahan tidak dipasang sebagai kode.

Qwen 0.8B Q8 `video-qwen08q8-parts-thinking256-v9` berhasil menyelesaikan
delapan bagian HTML, seluruh 41 aturan CSS desktop/mobile, state dan referensi
DOM, kemudian **gagal** pada fungsi waktu karena variabel dideklarasikan dua
kali. Percobaan `v10` menghasilkan fungsi valid sintaks tetapi salah untuk
pecahan detik/durasi panjang; patch model merusak kurung lalu dikembalikan.

Guard kini mengizinkan patch untuk galat parser deklarasi ganda yang diketahui
pada fungsi JS bernama lengkap, lalu memeriksa ulang seluruh sintaks sebelum
menerima sumber. Galat sintaks lain tetap memakai regenerasi bagian lengkap.
Diagnosis model yang terpotong disimpan sebagai bukti, tetapi tidak diteruskan
sebagai rencana yang dapat dipercaya. Kasus helper mencatat nilai aktual,
bukan hanya nilai yang diharapkan; hasil salah yang berubah nilainya tetap
dianggap kasus gagal yang sama saat memeriksa regresi.

Pada `v11`, konteks fungsi waktu diperkecil dan respons awal lolos semua kasus
selain input negatif (`-1` menghasilkan `-1:-1`). Model masih gagal memperbaiki
kasus tersebut dan kembali mendeklarasikan variabel yang sama. Ini tetap
**gagal**, bukan editor berfungsi. Pembanding LFM 1.17B `video-lfm-parts-v8`
gagal pada dokumen, dan DeepSeek Coder 1.3B `video-deepseek13-parts-v15` gagal
pada header. Sebanyak **127 tes lokal** terkait harness/proyek lolos; ini
tidak menggantikan bukti model nyata atau uji browser aplikasi lengkap.

Review browser draft UI `v11` merakit hanya bagian model yang lolos provenance,
tanpa menambahkan helper atau runtime buatan evaluator. Desktop 1280px memakai
font sistem dan tidak melebar horizontal, tetapi kontrol transport berada di
dalam area video. Pada viewport 390px, scroll width mencapai **457px**; layout
mobile **gagal**. Screenshot disimpan lokal sebagai
`browser-desktop-ui-failed.jpg` dan `browser-mobile-ui-failed.jpg`, bersama
`browser-ui-review.json`. Ini review tampilan parsial, bukan uji editor berfungsi.

Pemeriksaan HTML kini memverifikasi hubungan parent langsung antara area video,
transport dan kontrol, serta menolak `src` kosong sebelum video diimpor.
Kontrak CSS kini memeriksa properti/nilai desain yang sudah diminta di brief,
bukan sekadar selector dan sintaks. Properti tambahan yang mengubah layout
ditolak; prioritas `!important` juga diperiksa sesuai cascade. Kontrak ini
meminta model memperbaiki kodenya, tidak menulis CSS pengganti. Sebanyak
**129 tes lokal** terkait jalur tersebut lolos.

Putaran Qwen `v12` **gagal** pada panel preview: model kembali menambahkan
atribut `src`/`controls` dan tidak mempertahankan root `viewer`. Guard baru
menahan markup tersebut. Editor belum lengkap, belum menghasilkan ZIP yang
layak, dan belum lulus impor/playback/trim/ekspor di browser. Bukti draft UI
di atas tetap disimpan sebagai kegagalan, bukan screenshot demo sukses.

Panel HTML sekarang memakai JSON berisi string sumber dengan batas bentuk root;
isi panel tetap ditulis model. Pemeriksaan menolak tag HTML non-void yang
ditutup sendiri, misalnya `<video />`, karena browser memerlukan penutup
eksplisit. Atribut terlarang dapat diperbaiki lewat edit kecil: model memilih
potongan atribut yang sudah ada dan meminta penghapusan persis. Harness tidak
menambahkan markup pengganti. Pilihan ambigu ditolak; respons API/router tetap
divalidasi walaupun provider tidak mendukung constrained decoding. Hash sumber,
respons mentah dan rantai edit tetap diperiksa sebelum hasil dipakai kembali.

Qwen 0.8B Q8 `v13` masih gagal pada atribut preview. Putaran CPU nyata `v14`
berhasil memperbaiki preview: model menghapus atribut `src` lewat patch dan
panel lolos pemeriksaan. Putaran tetap **gagal setelah 253,2 detik** pada
timeline: respons terakhir terpotong sebelum JSON selesai. Belum ada editor
lengkap atau hasil ekspor yang layak. Sebanyak **138 tes terkait harness/proyek**
lolos di Windows, termasuk mekanisme yang sama untuk lokal/online/router;
ini tidak membuktikan kualitas semua model online atau fungsi editor di browser.

Putaran `v15` gagal setelah 140,4 detik pada ID timeline ganda. Ketika elemen
dengan ID benar memiliki jenis tag yang salah, harness kini meminta regenerasi
bagian lengkap. Untuk ID ganda, model dapat memilih nomor baris dan atribut ID
yang sudah ada untuk dihapus, tanpa menulis markup pengganti. Pilihan dibatasi
pada potongan asli dan diperiksa juga pada API online/router; replay provenance
memastikan semua byte tersisa tetap berasal dari model.

Putaran `v16` dihentikan setelah pemeriksaan sumber menemukan false positive:
panel timeline lolos guard lama tetapi memiliki penutup tag salah, atribut
ganda, kelas root berulang dan heading yang hilang. Ini dicatat sebagai
evaluasi terhenti dengan sumber tidak layak, bukan editor sukses. Guard fragment
kini memeriksa penutup eksplisit yang seimbang, atribut unik, dan satu root.
Kontrak timeline juga memeriksa heading dan parent kontrolnya. **145 tes
harness/proyek lolos di Windows**; uji ulang model nyata masih diperlukan.

`v17` tetap gagal setelah 97,5 detik: koreksi atribut timeline merusak markup,
dikembalikan ke sumber awal, lalu regenerasi JSON terpotong. Root tag yang
sudah disebut dalam tugas sekarang dapat dibatasi secara eksplisit oleh schema
dan guard, tanpa menawarkan alternatif tag yang tidak diminta. Timeline
memakai `section`; isi implementasi tetap ditulis model. Putaran `v18` sedang
diuji. Kelulusan guard bukan bukti layout atau fungsi; pemeriksaan sumber awal
`v18` masih menemukan pesan kosong yang ditulis sebagai atribut, bukan teks
terlihat. Aplikasi belum dinyatakan layak.

`v18` menyelesaikan HTML, seluruh 41 bagian CSS dan state; referensi DOM belum
selesai ketika batas harness tercapai setelah **900,11 detik**. Review browser
parsial: desktop 1280px memiliki scroll width 1280px, font sistem, dan transport
di luar permukaan video. Mobile 390px memiliki scroll width 375px (scrollbar
vertikal), tanpa overflow horizontal. Pesan awal timeline masih kosong karena
model menulisnya sebagai atribut. Screenshot `browser-desktop-ui-review.jpg`
dan `browser-mobile-ui-review.jpg` serta `browser-ui-review.json` disimpan pada
direktori evaluasi privat. Ini bukti layout parsial, bukan impor/trim/ekspor.

Guard sekarang memeriksa teks node DOM, sehingga kata dalam atribut atau
elemen lain tidak dapat memenuhi pesan yang diminta. Format JSON CSS juga
mendukung satu aturan di dalam media query, dan prompt selector memakai teks
CSS biasa untuk menghindari array JSON yang disalin menjadi selector.

`v19` gagal pada timeline setelah 51,4 detik. Timeline lalu dipecah menjadi
wadah, heading dan track; markup setiap bagian tetap ditulis model dan
assembler hanya menyambung tag/isi tersebut dengan whitespace. Jumlah bagian
menjadi **64**. Cache mencari hash tugas/sumber identik walaupun nomor bagian
bergeser; evaluator tetap mensyaratkan GGUF dan konfigurasi inferensi sama.
Bagian tidak cocok atau berubah tidak dipakai, dan sumber yang dipakai kembali
tetap menjalani guard terbaru.

`v20` gagal setelah 79,4 detik karena bug extractor: model menulis heading h2
yang benar, tetapi extractor hanya mengenali container. Dukungan h2 diperbaiki
dan diuji. Pada `v21`, model berhasil menulis seluruh timeline dengan pesan
aktual dan memakai kembali CSS tervalidasi. Putaran tetap gagal pada formatter
waktu setelah 213,2 detik: output salah untuk pecahan/negatif/Infinity, patch
tidak mengubah perilaku, dan regenerasi mencoba import modul.

Fungsi tunggal sekarang dapat memakai schema JSON yang membatasi nama dan
batas fungsi, tanpa menyediakan logika di dalamnya. Node dan tes perilaku
tetap memeriksa sumber. Prompt koreksi memakai sampai tiga contoh galat helper
serta jumlah diagnostik; jurnal mempertahankan diagnostik guard yang diterima
(hingga 12 contoh), dan seluruh kasus uji tetap dijalankan. `v22` masih gagal
setelah 108,9 detik pada sintaks/aritmetika formatter. **151 tes terkait
harness/proyek lolos di Windows**; belum ada editor lengkap yang lulus browser.

### Pemecahan helper dan konteks fungsi

Formatter kini dipecah menjadi tiga fungsi yang seluruh implementasinya tetap
ditulis model: normalisasi detik, format bilangan detik menjadi menit/detik,
dan penggabungan keduanya. Guard menguji normalisasi pada 51 input dan format
detik pada 50 input; pemeriksaan formatter akhir tetap memakai kasus pecahan,
negatif, NaN, Infinity, dan variasi nilai. Fixture penguji tidak dimasukkan ke
aplikasi. Dependensi pemeriksaan diambil dari bagian sumber model yang sudah
diterima, tanpa menyisipkan deklarasi app/ui atau implementasi buatan evaluator.

Prompt dapat membatasi daftar fungsi yang relevan. Fungsi murni tidak perlu
menerima signature helper lain, sedangkan formatter gabungan hanya menerima
signature kedua dependensinya. Deklarasi fungsi ganda dan helper tambahan
ditolak sebelum perakitan; model diminta menulis ulang bagian lengkap.
Pengujian jalur tersebut mencakup backend lokal, API online, dan router.

Bukti inferensi CPU nyata dengan Qwen3.5 0.8B Q8_0, reasoning 256:

- `v23` gagal normalisasi setelah 85,4 detik: NaN/Infinity tidak ditangani,
  patch merusak sintaks, dan respons pengganti terpotong.
- `v24` lolos normalisasi setelah instruksi dibuat berurutan. Formatter detik
  tetap gagal: padding hilang, patch tidak berubah, regenerasi terpotong.
- `v25` gagal setelah 69,4 detik. Konteks fungsi lebih kecil belum cukup:
  model menambah helper/duplikasi dan memakai string padding kosong.
- `v26` gagal setelah 85,5 detik. Percobaan pertama menulis fungsi dengan
  padding benar tetapi mengulang deklarasinya empat kali. Respons berikutnya
  kembali menambah helper; respons akhir mengembalikan Promise dan memanggil
  padStart yang tidak didefinisikan. Kegagalan tetap dilaporkan sebagai gagal.

Pembanding LFM2.5 1.17B Q4, profil sampling lfm25, `v9` gagal setelah 9,8 detik
pada dokumen: script app.js hilang, lalu regenerasi menghasilkan penjelasan.
Tidak ada ZIP editor berhasil dari putaran ini. **155 tes terkait lolos di
Windows**. Impor, playback, trim, teks dan ekspor WebM editor lengkap belum
terbukti. Eksperimen tetap opt-in; angka tes bukan bukti kualitas aplikasi
atau kecerdasan setara model besar.

### Perbaikan format respons dan pemilihan fungsi asli

Log runtime `v28` membuktikan bahwa regex `\s` pada schema sumber tidak
didukung konverter llama.cpp: konverter memperingatkan bahwa ia menerima
string apa pun. Karena itu, deskripsi schema pada putaran sebelumnya bukan
bukti bahwa batas pola benar-benar diterapkan saat sampling. Pemeriksaan
sintaks/perilaku setelah respons tetap menolak kode yang salah.
Rujukan: [konverter resmi llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/common/json-schema-to-grammar.cpp).

Percobaan pola karakter eksplisit `v29` berhasil menulis formatter detik yang
lolos 50 kasus, tetapi pola string kode yang luas juga mengizinkan batas kutip
JSON tertelan. Respons formatter gabungan memiliki kunci ganda; backend
akhirnya mengembalikan galat format 500 setelah 142,3 detik. Jalur sumber kini
menggunakan schema sederhana: satu properti string `source`, tanpa regex kode
di grammar. Schema tidak lagi disalin ke system prompt. Kontrak struktur,
nama fungsi, sintaks, serta perilaku diperiksa setelah JSON diurai.

Harness dapat memilih rentang fungsi yang benar-benar ditulis model untuk
helper yang memiliki tes perilaku. Acorn 8.15.0 membaca AST tanpa menjalankan
sumber model; fungsi dengan nama yang diminta dipilih menggunakan rentang
aslinya. Dua implementasi dengan nama sama yang berbeda ditolak, sedangkan
salinan yang persis identik dapat dipilih satu. Implementasi lain dan contoh
pemanggilan tidak ditambahkan ke aplikasi. Ini pemilihan sumber, bukan perbaikan
logika. Tes perilaku tetap harus lolos, dan replay cache/patch memeriksa sumber
mentah serta hash yang disimpan.

Parser juga membaca properti app/ui tingkat terluar, sehingga objek bersarang
tidak menyembunyikan field setelahnya dan deklarasi lokal tidak menggantikan
state global dalam konteks prompt. Acorn dibundel hanya untuk harness, bukan
dimasukkan ke proyek video hasil model: 241.575 byte, MIT, versi dipin, unduhan
diverifikasi dengan integrity npm dan hash berkas. Proses parser dibatasi
heap 96 MB, input 64 KiB, dan waktu 3 detik; tidak ada layanan baru atau
pemasangan npm saat aplikasi berjalan. Lisensi dan provenance ada di app/vendor.

`v27` tetap gagal setelah 135,6 detik karena padStart yang tidak didefinisikan;
`v28` gagal setelah 99,3 detik. Error identifier yang tidak didefinisikan kini
mengarahkan patch ke baris yang menyebut identifier tersebut. `v30` gagal
setelah 99,3 detik karena formatter menyalin helper lain dan respons terpotong.
Pada `v31`, formatter gabungan lolos pemeriksaan waktu dan setStatus lolos
pemeriksaan status. Putaran berhenti setelah 163,4 detik pada kontrol busy:
guard regex kita salah membaca app yang memiliki properti bersarang, sehingga
busy/loaded dianggap tidak didefinisikan. Pembacaan AST memperbaiki bug itu.
**167 tes terkait lolos di Windows**. Editor lengkap tetap belum terverifikasi
melalui impor, playback, trim dan ekspor WebM; eksperimen belum menjadi default.

Putaran CPU berikutnya tetap dicatat sebagai gagal:

- `v32`: 184,1 detik, kontrol busy tidak sesuai dan perbaikannya gagal.
- `v33`: 79,0 detik, visibilitas tombol batal salah; patch tidak mengubah sumber.
- `v34`: 329,4 detik, kontrol busy lolos matriks perilaku, tetapi impor media
  terpotong pada ketiga respons. Pemeriksaan berikutnya menemukan variabel
  tanpa deklarasi pada kontrol busy; kelulusan ini bukan bukti kode bebas galat.
- `v35`: 136,2 detik, pemeriksaan helper sudah menjalankan strict mode agar
  assignment ke variabel tanpa deklarasi ditolak. Model mengulang kode lalu
  menulis deklarasi app ganda, sehingga gagal sebelum impor. Konteks impor
  sudah dipersempit, tetapi perubahannya belum terbukti oleh inferensi berhasil.

Pemeriksaan ini berlaku pada jalur sumber lokal, API langsung, dan router.
Tes antar-backend memverifikasi jalur harness, bukan kualitas semua provider
online atau kemampuan setara model besar. Web dan Telegram menggunakan
agent.Turn yang sama. Tidak ada implementasi editor jadi yang disisipkan oleh
evaluator, dan sumber hasil model tidak diperbaiki manual agar benchmark lolos.

### Fungsi kecil, binding callable dan state bersama

Bagian tertentu dapat meminta sumber JavaScript langsung (`raw_source`),
tanpa string JSON. Format sumber disimpan dalam bukti dan replay cache;
kode tetap ditulis model, lalu diperiksa. Untuk fungsi yang tidak memerlukan
HTML, prompt tidak mengulang permintaan aplikasi lengkap: tugas bagian dan
kontrak dependensi sudah memuat kebutuhan yang relevan.

Parser mengenali fungsi deklarasi, arrow function, dan function expression
yang diikat ke nama tingkat terluar. Signature callable pada metadata dapat
dinormalisasi, tetapi byte kode keluaran tidak ditulis ulang. Helper bertes
dapat dipilih dari satu deklarasi variabel yang lengkap menggunakan rentang
AST aslinya; deklarasi dengan beberapa binding tidak dipotong secara tebakan.
Kode yang sekadar memberi angka/objek pada nama fungsi tidak dihitung callable.

Guard mendeteksi binding app/ui yang menimpa state bersama, termasuk parameter,
destructuring, variabel lokal, dan catch. Deklarasi state pertama tetap boleh.
Penimpaan state meminta regenerasi fungsi lengkap, bukan dua patch tanpa
perubahan. Impor dipisah menjadi releaseVideoUrls, videoMetadataReady,
videoLoadFailed, dan loadVideo. Tidak ada implementasi helper yang disisipkan.

Tes perilaku releaseVideoUrls memeriksa empat kombinasi URL: setiap URL yang
ada benar-benar dicabut tepat sekali, kedua field dikosongkan, state lain
dipertahankan. Tes videoLoadFailed memakai helper busy/status hasil model
yang sudah divalidasi untuk memastikan loaded/busy dibersihkan dan kelas
error diaktifkan. Fixture tersebut hanya penguji, tidak dikirim dalam aplikasi.
Tes ini belum menggantikan impor dan ekspor di browser nyata.

Bukti inferensi Qwen3.5 0.8B Q8_0 CPU, reasoning 256:

- `v36` gagal setelah 85,4 detik: variabel blocked tidak didefinisikan;
  patch tidak mengubah kode. Keluaran langsung lebih pendek, belum benar.
- `v37` gagal setelah 119,3 detik karena UI lokal bernilai null.
- `v38` kontrol busy lolos semua keadaan dalam strict mode, tetapi impor
  tetap gagal setelah 189,4 detik karena helper tambahan dan field rekaan.
- `v39` gagal setelah 125,9 detik. Metadata memakai binding arrow yang belum
  dikenali; respons berikutnya menambah export default yang tidak cocok.
- `v40` lolos sintaks hingga helper galat, gagal impor setelah 144,4 detik.
  Inspeksi sumber menemukan app/ui lokal kosong pada metadata. Guard baru
  menolak bagian tersebut meskipun pemeriksaan sintaks sebelumnya lolos.
- `v41` menolak cache pembersihan URL karena penimpaan app; gagal 48,8 detik.
- `v42` metadata memakai state bersama dengan benar, tetapi impor gagal
  setelah 139,8 detik. Inspeksi menemukan URL tidak dicabut dan penanda error
  tidak dipasang; keduanya kini mempunyai tes perilaku yang terpisah.

- `v43` pembersihan URL lolos empat kombinasi tes perilaku, bukan hanya sintaks.
  Putaran gagal setelah 78,0 detik pada penandaan error. Regenerasi penimpaan
  state ternyata belum aktif karena error ditambahkan setelah keputusan awal;
  urutannya diperbaiki dan diuji pada ketiga backend.
- `v44` tetap gagal setelah 55,2 detik. Regenerasi sudah berjalan, tetapi model
  memakai app.setBusy/app.setStatus yang tidak ada dan kembali menimpa app.

**178 tes terkait lolos di Windows.** Editor lengkap tetap belum terverifikasi.

### Konteks simbol dan perbaikan dokumen

Prompt JS kini membedakan field state luar yang sudah ada dari signature
helper standalone. Nama helper dipanggil langsung, bukan sebagai app/ui
method. Metadata AST untuk guard tidak berubah menjadi kode keluaran model.
Pemilihan field/helper relevan tetap berlaku pada generasi dan perbaikan.

Dokumen HTML yang utuh tetapi kehilangan aset dapat diperbaiki melalui
edit baris hasil model. Provenance menyimpan sumber awal dan patch, termasuk
replay melalui pemilihan container dokumen yang sama. HTML yang kehilangan
struktur setelah patch dipulihkan sebelum model diminta menulis ulang.
Guard aset melaporkan stylesheet atau script yang bermasalah secara terpisah;
script harus satu, classic, deferred, dan berada di head. Aset dalam komentar,
body, script module, atau duplikasi tidak dianggap memenuhi kontrak.

Grammar patch lokal tidak lagi memakai regex string replacement yang dapat
menelan batas kutip JSON. Batas baris dan pilihan nomor baris diperiksa setelah
JSON diurai pada ketiga backend. Patch dokumen boleh memakai replacement
multibaris; patch JS tetap dibatasi satu baris per edit. Fixture uji bukan kode
hasil editor. Tidak ada perubahan manual pada runtime aplikasi hasil model.

Bukti inferensi berikutnya:

- Qwen `v45`: helper galat video akhirnya lolos dengan helper status/busy
  hasil model, tetapi impor gagal setelah 116,0 detik: assignment tidak valid
  dan penulisan ulang helper yang sudah ada. Editor belum terbentuk lengkap.
- LFM2.5 1.17B Q4 CPU, profil lfm25, `v10`: gagal dokumen setelah 9,7 detik.
  Tautan script hilang, lalu regenerasi kehilangan title. Seluruh percobaan
  LFM dimulai dari awal tanpa cache atau campuran kode Qwen.
- LFM `v11`: galat backend 500 format peg-native setelah 11,6 detik pada patch.
- LFM `v12`: galat 500 tidak muncul, tetapi patch tidak mengubah kode; respons
  berikutnya bukan dokumen lengkap. Gagal setelah 10,0 detik.
- LFM `v13`: patch mengganti penutup HTML dengan teks instruksi, gagal setelah
  14,5 detik. Pelanggaran struktur kini memicu rollback, bukan diterima sebagai
  dasar patch berikutnya.
- LFM `v14`: rollback berjalan, tetapi regenerasi tetap bukan HTML lengkap;
  gagal setelah 9,8 detik. Perbaikan guard tidak sama dengan kelulusan model.

**189 tes terkait lolos di Windows.** Impor, playback, trim, overlay, ekspor
WebM baru dan tampilan editor lengkap tetap belum terbukti di browser nyata.


### Kontrak objek File dan pemanggilan helper

Harness bersama tetap dipakai pada backend lokal, online langsung dan router,
serta kanal web/Telegram. Uji kecil menjadi acuan kualitas; guard tidak
mengubah bobot model atau menjamin model kecil setara model frontier.
Bagian sumber tetap ditulis model, bukan runtime editor dari template.

Impor kini dipisah menjadi predicate File, pengikatan callback, assignment
sumber dan wrapper. Pemeriksaan VM menguji boolean MIME, callback tanpa
pemanggilan prematur, identitas File pada createObjectURL dan penutupan
link unduhan lama. Ini bukti unit perilaku, bukan bukti impor video browser.
Kontrak parameter juga diteruskan pada regenerasi.

AST menolak helper standalone yang dipanggil sebagai method objek, misalnya
preview.updateTimeline(). Nama helper yang baru akan ditulis pada bagian
berikutnya diberikan sebagai kontrak nama, tanpa menyisipkan implementasi.

Inferensi nyata Qwen3.5 0.8B Q8 CPU, reasoning 256:

- v46 gagal predicate File setelah 56,1 detik: objek dianggap string MIME.
- v47 gagal setelah 66,0 detik: operator in dipakai pada input primitif.
- v48 lolos pemeriksaan perilaku predicate, callback dan assignment sumber;
  wrapper impor lolos struktur/sintaks. Timeline gagal setelah 379,6 detik
  karena sumber terpotong dan field rekaan. Playback yang lolos sintaks
  masih memanggil preview.updateTimeline yang tidak ada.
- v49 menolak playback tersebut melalui AST. Perbaikan model kembali
  mendefinisikan helper lain; percobaan gagal setelah 76,8 detik.

**193 tes terkait lolos di Windows.** Belum ada editor lengkap yang lulus
impor/playback/trim/overlay/ekspor WebM nyata dan tinjauan desktop/mobile.


### Pemeriksaan Play dan scrub (8 Oktober 2026)

Percobaan v50 terputus bersama sesi sebelum laporan akhir ditulis. Sumber
playback yang sempat tersimpan lolos sintaks tetapi membalik kondisi paused,
tidak menunggu Promise play(), dan menolak input scrub berupa string angka.
Percobaan ini tidak dihitung sebagai kelulusan editor.

Play dan scrub dipisah agar model mengerjakan satu perilaku setiap bagian.
Pemeriksaan playback menunggu Promise di VM dengan batas waktu, menguji
kondisi paused/playing, batas trim, busy/unloaded, label tombol dan galat
pemutaran yang ditolak. Scrub diuji dengan string angka, nol, batas durasi,
nilai tidak finite, dan perlindungan busy/unloaded. Fixture tidak ikut
menjadi kode keluaran; model tetap menulis implementasinya sendiri.
Konteks timeline juga dibatasi ke state dan kontrol yang dipakai.


Pada v51, model tetap gagal setelah 126,1 detik karena await berada di fungsi
non-async, lalu regenerasi sempat menambahkan import modul yang tidak ada.
Jalur perbaikan sekarang mengizinkan patch deklarasi fungsi ketika parser
menunjukkan galat async tersebut. Hanya model yang menulis replacement;
patch masih wajib lolos sintaks, kontrak dan perilaku, serta disimpan untuk
replay provenance. Tes integrasi mencakup backend lokal, online dan router.

**198 tes terkait lolos di Windows** setelah pemeriksaan playback/scrub dan
jalur patch async ditambahkan. Ini belum membuktikan editor lengkap berfungsi.


v52 gagal setelah 127,6 detik. Play/Pause sudah lebih benar, tetapi penolakan
Promise pemutar tidak ditangani. Patch berikutnya hanya mengulang baris lama,
dan regenerasi menambahkan import rekaan. Jalur patch tanpa perubahan kini
mempertahankan sumber sebelumnya untuk satu percobaan diagnosis dan patch
terakhir, tetap dalam batas tiga percobaan bagian. Patch ditulis model,
perilaku diperiksa ulang, dan provenance hanya mencatat perubahan sah.

**201 tes terkait lolos di Windows** termasuk retry patch tanpa perubahan.


v53 gagal setelah 166,7 detik: kedua patch tetap tidak mengubah deklarasi
fungsi yang kehilangan async. Jalur perbaikan bekerja sesuai batas, tetapi
model belum berhasil memperbaiki sumber. Tidak ada ZIP editor yang diklaim
layak dari percobaan ini.

Commit 3137455 lolos **455 tes Linux** di GitHub Actions run 37714830909,
beserta pemeriksaan installer, supervisor, host setup, build gateway dan
pemindaian rahasia. Pengujian ini tidak mengakses VPS pengguna dan tidak
menggantikan benchmark perilaku editor di browser.


v54 memakai instruksi Promise chain, tetapi tetap gagal setelah 109,2 detik:
model memakai Play sebagai identifier yang tidak ada. Playback kemudian
dipisah menjadi callback sukses, callback galat, start, pause dan toggle.
Setiap operasi memiliki pemeriksaan perilaku; pemeriksaan start/toggle
menggabungkan helper hasil model yang telah lolos, bukan callback produksi
buatan evaluator. Uji penolakan Promise, batas trim dan guard tetap berlaku.

**202 tes terkait lolos di Windows** setelah pengujian komposisi playback.


v55 menyelesaikan callback sukses, callback galat, start dan pause dengan
kode asli Qwen 0.8B, semuanya lolos pemeriksaan perilaku. Pemeriksaan start
memakai kedua callback model yang benar-benar dihasilkan. Toggle gagal
setelah 230,5 detik karena cabang playing tidak memanggil pause. Editor
lengkap tetap belum lolos; scrub, timeline dan ekspor belum teruji nyata.


### Validasi trim terpisah (8 Oktober 2026)

v56 menyelesaikan toggle playback dan scrub. Keduanya lolos pemeriksaan
perilaku, termasuk komposisi callback/start/pause hasil model. Timeline
masih gagal setelah 437,2 detik: respons mengulang instruksi, terpotong,
dan kemudian memakai sintaks objek yang tidak valid sebagai fungsi.
Commit cb199d6 lolos **456 tes Linux** pada Actions run 37715870059.

Validasi trim kini dipisah menjadi predicate rentang, penerapan nilai valid,
penolakan nilai invalid dan penghubung kontrol. Pemeriksaan menguji angka
finite tanpa koersi pada predicate, batas 0 <= start < end <= duration,
input kontrol string, pelestarian rentang valid sebelumnya, pembaruan timeline
hanya untuk rentang valid, serta larangan mengaktifkan ekspor saat busy.
Gabungan validator memakai helper yang benar-benar dihasilkan model.
Render timeline tetap harus ditulis model dan dibuktikan di browser.

**204 tes terkait lolos di Windows** untuk perubahan validasi trim ini.


v57 gagal setelah 119,5 detik: predicate menerima start negatif, lalu patch
model merusak struktur fungsi. Harness memulihkan sumber sebelum patch.
Spesifikasi predicate diperjelas menjadi enam syarat Boolean terpisah;
implementasi dan perbaikannya tetap harus ditulis oleh model terpilih.


v58 meloloskan predicate trim, tetapi penerapan rentang gagal setelah 126,0
detik. Model menulis TypeScript dan pengulangan setStatus, sehingga sumber
tidak diterima sebagai JavaScript browser. Commit b7bfbff lolos **458 tes
Linux**, Actions run 37716940077.

Pemeriksaan ulang [model card resmi Qwen3.5 0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B)
pada 8 Oktober 2026 mengonfirmasi profil thinking untuk precise coding
sesuai parameter yang dipakai. Model card juga menyebut varian 0.8B lebih
rentan terhadap thinking loops, serta menyediakan profil non-thinking text.
Pembanding non-thinking dimulai dari awal tanpa cache kode thinking agar
hasil sampling tidak tercampur dalam satu klaim benchmark.


Pembanding non-thinking v59 dari awal gagal dalam 18,1 detik pada dokumen:
viewport, title dan aset tidak lengkap setelah percobaan perbaikan. Mode ini
belum menghasilkan editor yang lebih baik pada benchmark tersebut.

Konteks helper sekarang menampilkan nama callable tanpa awalan deklarasi
function, agar model tidak terdorong mendefinisikan ulang implementasi lama.
Instruksi bahasa menegaskan JavaScript browser classic tanpa anotasi
TypeScript. 204 tes Windows tetap lolos setelah perubahan konteks ini.


v60 menghasilkan JavaScript tanpa anotasi TypeScript, tetapi tetap gagal
setelah 104,3 detik: nilai start/end, pembatas busy dan durasi pesan tidak
diterapkan, sedangkan kedua patch tidak mengubah sumber. Konteks properti
kemudian diperjelas bahwa nilai boleh dibaca/ditulis sesuai tugas sambil
mempertahankan objek app/ui yang sudah ada. Guard terhadap shadowing objek
state tetap berjalan; ini perubahan instruksi, bukan pengisian kode model.


v61 menyimpan start/end dengan benar tetapi gagal setelah 111,1 detik karena
memakai busy tanpa app. Kedua patch tidak mengubah baris tersebut.

Audit jalur pemulihan menemukan bug terpisah yang direproduksi dengan tes:
setelah ReferenceError diperbaiki, assertion yang baru dapat dijalankan
keliru dianggap regresi dan patch dipulihkan. Pemeriksaan kini membedakan
galat eksekusi dari kegagalan assertion yang selesai. Tes lokal/online/router
membuktikan dua patch bertahap dapat diperiksa dan direplay tanpa rollback
keliru. Patch yang memperkenalkan galat eksekusi ke helper yang sebelumnya
menyelesaikan seluruh pemeriksaan tetap dipulihkan. Tes juga mencakup galat
async, bukan hanya ReferenceError sinkron. Semua keluaran tetap ditolak
sampai tidak ada galat; perbaikan ini tidak melewati pemeriksaan perilaku.

**209 tes terkait lolos di Windows** setelah perbaikan klasifikasi galat.

## Pemisahan operasi trim dan pemeriksaan durasi

v62 gagal setelah 88,5 detik pada applyTrim: penyimpanan nilai, pesan durasi
dan pembatas ekspor saat busy belum benar. Operasi ini kemudian dipisahkan
menjadi storeTrim, refreshTrimExport dan reportTrim, dengan pemeriksaan
gabungan applyTrim tetap dijalankan. Ini instruksi bagi model, bukan kode
runtime buatan evaluator.

v63 (Qwen3.5 0.8B Q8_0, thinking 256) berhasil menghasilkan storeTrim yang
lolos pemeriksaan, tetapi gagal setelah 136,9 detik pada refreshTrimExport.
Model membalik arah penugasan; perbaikannya belum menjaga state dan kontrol
ekspor. Tidak ada editor lengkap yang lulus dari percobaan ini.

Tes negatif menemukan bahwa pemeriksaan pesan durasi berbasis substring
dapat menerima -10 sebagai 10. Pemeriksaan sekarang membandingkan satu
nilai numerik bertanda secara utuh; durasi negatif, kelipatan sepuluh dan
nilai yang meleset ditolak pada helper maupun komposisinya.

210 tes terkait lolos di Windows. CI Linux pada commit 07b52ec sebelumnya
lolos 463 tes; angka itu belum mencakup pemisahan operasi trim terbaru.


v64 memperjelas refreshTrimExport sebagai perilaku tombol dan menandai
app state read-only. Model menghasilkan fungsi baru yang lolos pemeriksaan
pada percobaan pertama. Namun reportTrim gagal: menampilkan teks end-start
tanpa menghitungnya, memanggil status dua kali, lalu menghasilkan patch
tanpa perubahan. Total 135,7 detik; belum ada editor lengkap.

Umpan balik reportTrim kini menyertakan input, durasi yang diharapkan dan
panggilan status aktual (dibatasi panjangnya). Identitas kasus tetap stabil
ketika nilai aktual berubah, sehingga tidak dianggap regresi baru. v65 tetap
gagal setelah 128,3 detik: pesan hanya berisi trim dan timeline tidak
diperbarui. Ini bukti keterbatasan hasil model, bukan keberhasilan editor.

211 tes terkait lolos di Windows sebelum penyesuaian penanda diagnostik;
tes trim dan identitas kasus dijalankan ulang sesudahnya. CI Linux a0c9ee8
lolos 464 tes; perubahan v64/v65 belum termasuk dalam angka Linux itu.

## Memisahkan arti contoh tes dari tindakan runtime

Diagnosis model pada v65 salah mengartikan dua input uji sebagai dua
panggilan status dalam satu fungsi. Konteks diagnosis dan patch kini
menegaskan bahwa tiap contoh adalah pemanggilan terpisah; perbaikan harus
umum dan tidak boleh hard-code nilai contoh. Tes jalur lokal/online/router
memeriksa konteks yang sama diteruskan ke kedua tahap.

Instruksi reportTrim juga diubah menjadi urutan menghitung nilai lokal,
membangun pesan, memanggil setStatus, lalu updateTimeline, tanpa batas
empat baris. v66 menghasilkan implementasi model yang benar pada percobaan
pertama; trim_report, trim_apply dan trim_reject lolos pemeriksaan perilaku.
Kode runtime tetap berasal dari model lokal, bukan dari fixture evaluator.

Percobaan v66 berakhir setelah 251,5 detik pada validateTrim: keluaran awal
hanya mengembalikan predicate tanpa memanggil applyTrim/rejectTrim. Perbaikan
terakhir mencoba mendeklarasikan ulang app sehingga ditolak. Timeline,
ekspor dan browser end-to-end belum lulus; editor tidak dinyatakan selesai.

214 tes terkait Windows lolos pada perubahan v66. CI Linux commit 56c0bfd
lolos 465 tes (sebelum perubahan konteks contoh pada v66).

## Penghubung trim dan pecahan detik

Instruksi validateTrim diubah menjadi dua cabang perilaku yang eksplisit
dan mempertahankan state luar. v67 menghasilkan penghubung yang memanggil
applyTrim/rejectTrim dengan benar, tetapi parsing menggunakan parseInt
menghilangkan pecahan detik. Tes menolak keluaran itu; patch pertama hanya
menghapus baris kosong dan belum memperbaiki perilaku.

Enam tes trim/recipe lolos setelah perubahan instruksi. CI Linux pada
commit 7b39e36 lolos 468 tes; bukan bukti editor hasil model sudah berfungsi.

V67 berakhir setelah 333,5 detik dengan kesalahan pecahan detik yang sama.
Pesan validasi kini memuat pasangan waktu yang diharapkan dan tersimpan,
dengan identitas kasus stabil saat nilai aktual berubah. Tes regresi
memastikan parseInt ditolak untuk 1,25 sampai 3,75 detik dan diagnosis
menampilkan nilai 1 dan 3 yang benar-benar tersimpan.

## Menyaring konteks perbaikan

v68 gagal setelah 228,6 detik. Keluaran awal mengirim Boolean sebagai
argumen applyTrim; patch berikutnya menyalin metadata evaluator seperti
raw_source, behavior_checks dan generation_contract_revision ke JavaScript.
Patch tidak valid ditolak, tetapi konteksnya sendiri terlalu bercampur.

Kontrak perbaikan kini memakai daftar bidang yang memang menjelaskan kode
(function, parameter, state yang boleh ditulis, kontrol HTML, aturan CSS).
Metadata evaluator/cache tidak disertakan. Simbol outer dan helper tetap
dijelaskan melalui konteks JavaScript. Tes regresi mencakup kontrak JS,
HTML dan CSS serta mempertahankan batas state read-only.

215 tes terkait Windows lolos setelah penyaringan konteks. Uji nyata v69
berakhir gagal setelah 178,3 detik: model mendefinisikan ulang helper, lalu
pada perbaikan memanggil rejectTrim sebagai metode objek. Guard tetap
menolak keluaran itu. Penyaringan konteks belum membuktikan editor berhasil.
CI Linux untuk commit 7efc940 sebelumnya lolos 468 tes.

## Pemulihan setelah patch tanpa perubahan

v70 gagal setelah 154,9 detik: validateTrim mempertahankan pecahan detik
tetapi langsung menerapkan trim tanpa memeriksa rentang. Patch pertama
tidak mengubah sumber; diagnosis berikutnya berulang dan keliru, lalu
patch melanggar format baris.

Setelah patch ditolak karena tidak mengubah sumber, percobaan terakhir kini
meminta penulisan ulang bagian tersebut dari spesifikasi dan galat aktual.
Batas tiga percobaan tetap berlaku, seluruh pemeriksaan tetap dijalankan,
dan kode lama/patch gagal tetap tersimpan di jurnal. Sumber baru tidak
dicatat sebagai replay patch lama. Tes lokal/online/router membuktikan
alur tiga panggilan model dan validasi sumber baru; ini menggantikan jalur
diagnosis-plus-patch setelah no-op yang didokumentasikan sebelumnya.

V71 menulis validateTrim dengan benar pada percobaan pertama: Number
mempertahankan pecahan, kedua cabang memanggil helper yang sesuai dan
mengembalikan hasil. video_trim lolos dengan helper model yang sudah
tervalidasi. Keberhasilan itu bukan akibat jalur fallback no-op; fallback
diverifikasi terpisah oleh tes.

V71 berakhir gagal setelah 638,1 detik pada kanvas ekspor (keluaran
terpotong, deklarasi ulang app/helper). Timeline sempat lolos sintaks tetapi
menggunakan innerHTML untuk nama berkas/teks serta menumpuk elemen.
Pemeriksaan DOM terbatas kini menolak keluaran nyata tersebut, memeriksa
dua jalur, posisi klip/playhead, durasi aktual, scrub, penghapusan caption,
unload dan render ulang tanpa pertumbuhan node. Fixture bukan browser dan
tidak menggantikan pengujian media nyata. Tes memakai implementasi referensi
hanya di tests; fixture/kode referensi tidak diberikan kepada model atau
disisipkan ke aplikasi hasil.

Konteks overlay dan kanvas dipersempit ke simbol yang diperlukan, dengan
keluaran JavaScript langsung. CI Linux commit 95eb52c lolos 469 tes.

217 tes terkait Windows lolos setelah pemeriksaan DOM dan fallback baru.
Pemeriksaan langsung pada sumber timeline v71 menolak pemakaian innerHTML.

## Timeline dalam helper kecil

v72 gagal setelah 175,6 detik pada timeline monolitik (placeholder dan
ui.filename yang tidak ada). Instruksi dipecah menjadi elemen teks,
playhead, klip video, klip caption, track dan komposisi timeline. Seluruh
kode tetap harus ditulis model; fixture referensi hanya menguji evaluator.

Runner DOM kini hanya menyertakan kasus yang dipilih. Memuat semua fixture
sekaligus sempat melewati batas command-line Windows (WinError 206);
pemilihan per kasus memperbaikinya tanpa melonggarkan sandbox. Posisi CSS
diperiksa dengan satuan persen; px tidak diterima sebagai persentase.

218 tes terkait Windows lolos. V73 berhasil menulis helper elemen setelah
patch tanpa perubahan diikuti regenerasi yang valid, membuktikan fallback
baru pada model nyata. Namun playhead gagal setelah total 131,5 detik: nama
kelas timeline-element keliru, walaupun perhitungan persentase benar.
Pesan pemeriksaan kemudian dipisah per properti agar menyebut kelas yang
salah, bukan menuduh kalkulasi posisi. Pemeriksaan ulang sumber nyata
menghasilkan hanya kegagalan className. Tiga tes timeline lolos sesudahnya.
Fixture juga membedakan setAttribute class yang sah dari className yang
bukan atribut kelas HTML. CI Linux df91625 sebelumnya lolos 471 tes.
Editor lengkap belum lulus; pengujian browser/ekspor nyata masih diperlukan.

## Elemen DOM, teks literal, dan hasil helper

v74 gagal setelah 120,2 detik pada playhead: posisi diletakkan dalam teks
markup, bukan properti style elemen. Kontrak pemanggil kemudian menjelaskan
bahwa makeTimelineElement mengembalikan elemen DOM dan argumen teksnya
selalu literal. v75 akhirnya menulis playhead yang benar pada percobaan
ketiga. Kode model dan pemeriksaan posisi/kelas tersimpan dalam jurnal.

v75 berhenti pada klip video setelah 180,8 detik. Posisi kiri keliru dan
mengandung titik koma sebagai bagian nilai CSS. Fixture sebelumnya juga
keliru tidak mengenali innerText yang sah; kini innerText diperlakukan
sebagai teks, seperti textContent. Persentase numerik setara (misalnya
25.0%) diterima, sedangkan px, nilai salah dan persen bertitik koma tetap
ditolak. Return string CSS mendapat pesan wajib mengembalikan elemen DOM,
bukan galat akses properti yang tidak jelas. Tes mencakup variasi tersebut.

Pemeriksaan ulang sumber klip video nyata hanya melaporkan posisi kiri
yang salah, tanpa lagi menuduh teks aman sebagai galat. 218 tes terkait
Windows lolos. CI Linux commit 4a9905f berhasil; unduhan log terputus
sehingga jumlah tes Linux tidak diklaim dari run itu.

V76 gagal setelah 130,3 detik karena fixture belum memiliki classList.add.
Fixture kini mendukung add/remove/contains/toggle yang mengikuti className.
Tiga tes timeline lolos sesudahnya, termasuk jalur className, atribut class,
classList, innerText dan variasi persen. Pemeriksaan ulang sumber model v76
tidak lagi melempar galat API: ia melaporkan lebar 10% yang seharusnya
100%/40%, kiri 2,5% yang seharusnya 25%, serta teks durasi total yang keliru
menggantikan durasi terpilih. Jadi sumber model tetap gagal karena perilaku
aktualnya, bukan karena API DOM yang sah tidak tersedia pada fixture.

## Hitungan timeline dan kontrak argumen

V77 gagal setelah 113,5 detik: keluaran klip video tidak mempunyai deklarasi
fungsi lengkap. Pemeriksaan durasi juga ditemukan terlalu longgar:
pencarian substring menerima 100 sebagai 10. Pemeriksaan kini mencocokkan
token angka setelah menghapus nama berkas literal, menolak durasi sepuluh
kali lipat serta durasi negatif. Posisi klip diuji dengan durasi video 10
dan 20 detik agar pembagi tetap 10 tidak lolos.

V78 berhasil menulis timelinePercent dan timelineSelectedSeconds dengan
Qwen3.5 0.8B Q8_0 pada CPU, memakai reasoning budget 256. Keduanya lolos
pemeriksaan beberapa durasi dan batas pecahan. Implementasi tetap berasal
dari inferensi model; kode referensi tes tidak disisipkan ke hasil.
Pemanggil klip video masih gagal: durasi ditempatkan pada argumen keempat
factory tiga argumen sehingga tidak tampil. Regenerasi kemudian menghasilkan
export dan TypeScript yang tidak cocok dengan skrip browser klasik.
Run berakhir gagal setelah 257,9 detik; editor lengkap belum tersedia.

Instruksi berikutnya memperjelas bahwa nama berkas dan durasi harus digabung
menjadi satu argumen teks, serta helper persen sudah mengembalikan satuan.
219 tes terkait di Windows lolos sebelum perluasan kasus durasi; empat tes
timeline lolos setelah perluasan tersebut. CI Linux commit 68da151 berhasil;
jumlah tes tidak diklaim tanpa pemeriksaan log. Fixture DOM dan tes ini tetap
tidak menggantikan verifikasi impor/ekspor media dan tampilan browser nyata.

V79 gagal setelah 98,5 detik. Teks klip sudah berisi durasi yang benar,
namun posisi/lebarnya hilang dan patch merusak sintaks. Pengaturan batas
timeline kemudian menjadi helper bersama setTimelineClipBounds, dipakai
klip video dan klip teks. Pemeriksa menguji dua durasi, identitas elemen yang
dikembalikan, posisi, lebar serta pelestarian teks/style lain. Klip video
juga harus memakai elemen div. Lima tes timeline lolos sesudah perubahan.
Ini pemecahan spesifikasi dan pemeriksaan, bukan penyisipan implementasi.

V80 menulis setTimelineClipBounds yang benar pada percobaan pertama (27,0
detik inferensi), tetapi pemanggil mengubah kelas dan menambahkan style yang
tidak diminta. Patch/regenerasi tidak menyelesaikannya; run gagal setelah
194,1 detik. 220 tes terkait Windows lolos pada revisi tersebut.

Pemanggil dapat meminta konteks implementasi helper yang sudah ditulis model
dan diterima pemeriksa, lewat include_helper_sources. Hanya helper relevan
yang sudah tersedia diteruskan, tanpa implementasi referensi tes. Konteks
dibatasi 2.400 karakter; helper besar dilewati seluruhnya, bukan dipotong.
Konteks yang sama tersedia pada pembuatan, patch dan regenerasi serta pada
backend lokal/online/router. Helper wajib tetap dipanggil, bukan didefinisikan
ulang. Sembilan tes timeline/konteks lolos; tes routing memakai mock model
dan tidak membuktikan kualitas provider online nyata.

V81 berhasil menulis klip video pada percobaan pertama (30,3 detik), memakai
helper model yang sudah divalidasi. Klip teks awal juga lolos fixture lama,
tetapi pemeriksaan lebih lengkap kemudian menemukan bahwa trim() menghapus
spasi pada teks yang seharusnya dipertahankan. Fixture/instruksi kini menguji
teks asli termasuk spasi dan dua durasi video. Pemeriksaan ulang kode v81
menolak perubahan teks itu. Run v81 sendiri gagal setelah 193,7 detik pada
baris track: label/lane tidak terpasang dan perbaikan menghasilkan deklarasi
ganda lalu kode terpotong. Konteks helper tervalidasi juga diaktifkan untuk
track, dengan parameter label dan clip dijelaskan. 224 tes terkait Windows
lolos sebelum perluasan caption, dan sembilan tes terkait lolos sesudahnya.

V82 menulis caption yang mempertahankan teks asli (19,0 detik) dan baris
track yang benar (22,2 detik), keduanya pada percobaan pertama. Komposisi
timeline belum benar: ruler menampilkan nama panggilan formatTime sebagai
teks dan kondisi unloaded tidak memberi pesan atau membersihkan track.
Rollback menolak patch yang menambah kegagalan; run berakhir gagal setelah
207,7 detik. Konteks helper/instruksi kini diterapkan pada komposisi, dan
fixture menuntut tepat satu ruler serta dua track, bukan node tambahan.
227 tes terkait Windows lolos sebelum perluasan komposisi; 12 tes fokus
lolos sesudahnya, termasuk konteks helper pada patch/regenerasi untuk tiga
backend. Pemindaian seluruh riwayat Git dengan Gitleaks menemukan 0 temuan.

V83 berhasil menulis updateTimeline pada percobaan pertama (29,2 detik).
Pemeriksaan komposisi lolos: tepat satu ruler, dua jalur, posisi/teks,
sinkronisasi scrub, render ulang tanpa node bertambah serta pembersihan
saat unloaded. Ini masih fixture terbatas, belum bukti browser/ekspor.
Run berhenti gagal setelah 124,9 detik pada updateText: model mendeklarasikan
ui berulang, lalu melakukan shadowing dan mengakses ui.querySelector yang
bukan bagian kontrak. Timeline tersimpan sebagai kode model yang terverifikasi
pada tahap ini; overlay, kanvas, encoder, binding kontrol dan verifikasi
browser/ekspor/mobile masih harus diselesaikan. Tidak ada ZIP editor layak
yang dipublikasikan dari run ini.

## Overlay dan frame ekspor

V84 menghasilkan fungsi overlay yang lengkap, tetapi menghapus input yang
hanya berisi spasi. Patch mengganti baris hidden, menambah kegagalan, dan
regenerasi melakukan shadowing app/ui; run gagal setelah 105,8 detik.
Pemeriksa kini menunjukkan properti, input yang diharapkan dan nilai aktual.
Editor patch mengenali diagnostik teks/nilai dan menawarkan baris akses
properti tersebut (termasuk alias dan bracket), tanpa memilih penggantinya.
Regresi mereproduksi sumber v84 dan memastikan baris visibility tidak ikut
menjadi sasaran galat textContent.

V85 menulis badan overlay tanpa deklarasi pada percobaan awal, lalu berhasil
menulis updateText lengkap melalui regenerasi (20,9 detik). Teks literal,
spasi, visibilitas dan refresh hanya ketika loaded lolos pemeriksaan.
Run kemudian gagal setelah 235,1 detik pada kanvas: fungsi tercampur,
deklarasi/state baru, app.preview yang tidak ada dan keluaran terpotong.
229 tes terkait Windows lolos pada revisi ini. CI Linux commit 0c8da60
berhasil; log run 37727970416 mengonfirmasi 481 tes Python lolos.

Persiapan kanvas dan penggambaran frame kini merupakan dua tugas model.
Fixture baru memeriksa ukuran maksimal 720px, rasio landscape/portrait,
dimensi invalid, 2d tidak tersedia, serta pelestarian state saat galat.
Frame harus memakai preview nyata, caption asli, ukuran/font/alignment,
white fill dan outline/shadow untuk kontras. Save/restore dan format warna
hex/RGB/RGBA yang setara didukung. Referensi ada hanya di tes; tidak diberikan
kepada model atau disisipkan ke hasil. Hash fixture DOM/kanvas kini ikut
laporan evaluator. Pemeriksaan ini tetap tidak membuktikan video WebM baru
atau tampilan browser; keduanya masih memerlukan uji media/browser nyata.

V86 akhirnya menulis prepareCanvas yang benar pada percobaan ketiga:
dimensi finite/positif, ukuran proporsional, context 2d dan penyimpanan state
setelah pemeriksaan. Paint frame masih gagal pada koordinat, font tanpa
ukuran px, warna, kontras dan teks yang dipangkas. Run tercatat gagal setelah
229,3 detik. Cetak ringkasan kemudian gagal pada codec konsol Windows cp1252
untuk teks Jepang; results.json UTF-8 sudah tersimpan dan server tetap
dihentikan lewat finally. Ringkasan kini ASCII-safe; tes subprocess cp1252
membuktikan JSON mengembalikan teks Unicode asli. Failures tidak berubah
menjadi sukses dan laporan berkas tetap menyimpan Unicode penuh.

Pengaturan gaya caption kini satu helper model terpisah, diuji pada enam
lebar kanvas. Paint frame memakai helper yang sudah tervalidasi dan harus
memakai teks asli serta posisi/max width yang benar. Fixture video memiliki
metadata siap untuk menerima guard preview yang sah; dimensi invalid diuji
pada kedua sumbu. 231 tes terkait Windows lolos sebelum pemecahan gaya,
dan empat tes kanvas/konsol lolos sesudahnya. Editor lengkap belum lulus.

V87 gagal setelah 149,7 detik: frame tidak menggambar preview dan fillText
tidak menerima argumen batas lebar. Instruksi frame kini menyebut urutan
argumen API, termasuk menggambar video sebelum pemeriksaan caption kosong.
233 tes terkait Windows lolos pada revisi tersebut.

Kasus font diperluas dengan lebar 590, 610 dan 1019 agar membedakan nearest,
floor dan ceil. Pemeriksaan ulang kode gaya v87 membuktikan pembulatan floor
yang sebelumnya lolos kasus terlalu sempit. V88 gagal setelah 144,4 detik:
patch pertama mengubah baris font tanpa memperbaiki rumus; patch berikutnya
mengganti floor menjadi ceil, menimbulkan kegagalan baru dan dikembalikan.
233 tes regresi Windows lolos setelah uji tersebut. Status tetap gagal;
tidak ada klaim browser, ekspor WebM atau editor lengkap telah lulus.

Diagnostik properti terhitung sekarang dapat memilih assignment asli beserta
deklarasi/assignment lokal yang menjadi inputnya lewat parser Acorn. Ini
analisis statis terbatas, bukan eksekusi atau kode pengganti. Nama ambigu
antarscope disertakan konservatif; parser gagal memakai jalur perbaikan
biasa. Tes mereproduksi rumus font v88, bracket access, assignment terpisah
dan keluaran parser gagal. Jalur request yang sama diperiksa untuk lokal,
API langsung dan router; mock ini tidak membuktikan koneksi provider nyata.

V89 gagal setelah 192,9 detik. Regenerasi membuat konstanta ukuran teks yang
kemudian ditulis ulang; patch model berikutnya memakai nama variabel yang
tidak terdefinisi. Permintaan pertama juga meniru konteks app/ui yang tidak
dibutuhkan helper berparameter. Konteks simbol kosong kini dihilangkan;
kontrak helper berparameter tidak memperkenalkan state aplikasi. 237 tes
regresi Windows dan lima tes konteks terarah lolos sebelum uji ulang v90.
Pemangkasan konteks tidak memasukkan implementasi atau melonggarkan perilaku.

V90 gagal setelah 113,6 detik. Helper pertama tidak melakukan clamp minimum;
patch tidak mengubah sumber dan ditolak, lalu regenerasi menulis ulang
konstanta. 238 tes regresi Windows lolos. Selektor baris perbaikan kini juga
mengaitkan galat assignment konstanta dengan deklarasi/write asli (termasuk
increment), tanpa mengganti binding sendiri. Enam tes terarah lolos setelah
perubahan ini. Pemeriksaan secret scan riwayat menghasilkan nol temuan.

V91 gagal setelah 112,5 detik. Respons terakhir sudah menghitung nearest
dan minimum serta mengatur properti canvas, tetapi berupa method header
tanpa kata kunci function. 239 tes regresi Windows lolos sebelum penambahan
checkpoint. Harness mengenali bentuk ini sebagai sasaran perbaikan header
oleh model; tidak menambahkan kata kunci sendiri atau menjalankan kode rusak.

Evaluator memiliki opt-in `--resume-failed-parts` bersama `--resume-parts`.
Bobot, chat serialization, pre-tokenizer, sampling dan thinking tetap harus
sama. Untuk respons gagal legacy, hash seluruh recipe juga harus identik.
Hanya respons JS asli lengkap, bukan patch/truncated, yang bisa disimpan
sebagai kandidat; raw decoding/selection harus persis cocok dengan source.
Kandidat diberi status gagal, dicetak dalam log, dan diperiksa kembali lewat
jalur generator biasa. Tidak berarti bagian tersebut sudah lolos. Respons
patch berikutnya harus tetap berasal dari model dan tercatat dalam provenance.

V92 memakai checkpoint v91, tetapi model mengirim ulang seluruh badan pada
edit header, sehingga batas satu baris menolaknya. Regenerasi berikutnya
menulis statement tanpa fungsi; run gagal setelah 90,6 detik. 241 tes regresi
Windows lolos. Request perbaikan deklarasi sekarang hanya menampilkan header
asli dan ruang lingkup sintaks; badan tetap disimpan untuk penerapan patch
dan pemeriksaan. Tidak ada kata kunci yang disisipkan evaluator. Dua tes
terarah lolos sesudah perubahan konteks header.

V93 akhirnya meloloskan gaya caption: model menulis patch header sendiri
(19,0 detik), lalu keenam lebar kanvas lolos. Raw respons, asal badan fungsi
dan hash chain tersimpan. Run tetap gagal setelah 174,1 detik karena frame
memakai ctx/originalUI yang tidak terdefinisi dan menyalin pengaturan gaya;
patch hanya mengubah satu referensi lalu kembali ke referensi salah.

Jika patch mengubah teks tetapi menyisakan kumpulan galat helper yang sama,
percobaan terakhir kini menulis sumber baru dari kontrak/galat alih-alih
mengulangi patch. Perubahan ini tidak memperbesar batas tiga percobaan.
Frame mendapat signature helper gaya tanpa badan implementasinya, karena
pemanggil cukup memakai API tersebut. Tujuh tes terarah lolos. CI Linux
commit 69c21d6 run 37732732302 berhasil; log mengonfirmasi 495 tes Python
lolos dalam container Linux. Secret scan commit tersebut juga berhasil.

V94 gagal setelah 141,7 detik. Regenerasi menghilangkan properti app.ui yang
salah tetapi menggambar video hanya untuk caption nonkosong, membagi posisi
x dua kali, menghilangkan maxWidth dan tidak memanggil helper gaya. 242 tes
regresi Windows lolos. Konteks simbol sekarang hanya menampilkan path yang
benar dan signature standalone; tidak mengulang contoh property yang dilarang.
Diagnostik shared field menunjuk baris akses property itu saja.

Frame kini terdiri dari drawPreviewFrame, paintCaption dan paintFrame sebagai
penggabung. V95 meloloskan lapisan video pada percobaan pertama model (24,6
detik menurut respons). Lapisan caption masih membagi posisi x dua kali dan
tidak mengirim maxWidth; patch menyalin return yang tidak terkait, regenerasi
menambah ui.video yang tidak ada. Run gagal setelah 158,2 detik. 244 tes
regresi Windows lolos. Frame gabungan tetap memakai assertion caption/video
lengkap, termasuk urutan video sebelum teks dan larangan menghapus frame.

Selektor patch mengikuti panggilan API bernama beserta input lokalnya pada
galat argumen. Untuk kasus ini, prompt hanya memuat statement yang terkena
dan baris input asli, dengan nomor baris asli untuk penerapan patch; komentar
panjang dan statement lain tetap disimpan tanpa ditampilkan ulang. Pemilihan
checkpoint gagal juga mempertimbangkan galat yang benar-benar tercatat pada
hash source yang sama: header yang bisa diperbaiki atau behavior checks yang
selesai didahulukan dari galat eksekusi/struktur. Seluruh kandidat tetap
diperiksa ulang. Empat tes terarah lolos setelah perubahan ini.

V96 meloloskan paintCaption dari regenerasi model dan paintFrame gabungan.
Ekspor monolitik masih gagal: ketiga respons JSON source terpotong; run
berakhir setelah 524,3 detik tanpa aplikasi selesai. 246 tes regresi Windows
lolos sebelum perubahan ekspor. Draft memiliki panel media, preview,
inspektor dan timeline; observasi browser pada lebar 390px tidak menemukan
overflow horizontal (scrollWidth 375px). Kontrol belum terhubung karena
initEditor belum dihasilkan, sehingga ini bukan bukti fungsi editor selesai.

Untuk v97, tugas ekspor dipecah menjadi delapan helper: MIME, seek dengan
timeout, audio yang bisa dipakai ulang, cleanup, finalisasi blob, callback
recorder, loop frame dan orkestrasi. Recipe tetap hanya berisi instruksi,
bukan kode aplikasi. Fixture terpisah memeriksa lifecycle dengan API palsu
di sandbox: MIME tidak didukung, timeout/galat seek, reuse audio, fallback
silent, video-track cleanup, RAF handle nol, blob kosong/cancel/error,
urutan recorder-start sebelum playback dan stop pada batas trim. 21 tes
checker, termasuk mutasi yang harus gagal, lolos. Pemeriksaan ini bukan
bukti MediaRecorder atau ekspor audio bekerja di browser nyata.

V97 berhenti setelah 37,9 detik sebelum kode ekspor: fixture frame gabungan
melampaui batas panjang command line Windows (WinError 206). Tiga dari 208
tes regresi juga menemukan batas yang sama. Fixture terpilih sekarang dikirim
sebagai data JSON lewat stdin; command runner tetap sama untuk semua kasus.
22 tes ekspor/transport lolos setelah perbaikan, termasuk batas panjang command
dan pemeriksaan bahwa fixture tidak menjadi kode aplikasi. Benchmark v98
memakai sumber model yang sudah lolos v96 dan memeriksanya kembali.

V98 melewati pemeriksaan frame gabungan, tetapi gagal pada pemilihan MIME
setelah 115,8 detik. Respons pertama memisahkan MIME/codec menjadi dua argumen
dan memilih plain WebM lebih dahulu. Regenerasi memperbaiki argumen/throw,
namun urutan plain WebM masih salah. Diagnostik kini mencantumkan MIME yang
diharapkan dan yang dikembalikan; task mengutip tiga string utuh secara jelas.
22 tes ekspor tetap lolos. Suite lengkap Windows: 513 lolos, 9 gagal pada
ekspektasi khusus POSIX/Linux (pipeline shell, chmod, lokasi login host,
supervisor Linux dan skrip bash/uninstall). Tidak memasang WSL; cakupan Linux
tetap dibuktikan melalui GitHub Actions, bukan menyatakan suite ini hijau.

CI Linux commit ae833eb berhasil: run 37736082595 mencatat 522 tes Python
lolos (69,81 detik), serta gateway, sintaks, packaging, installer, supervisor
dan host setup. Secret scan commit tersebut berhasil. Hasil ini tidak membuktikan
perilaku editor yang masih belum selesai.

V99 gagal setelah 104,4 detik. Respons pertama sebenarnya berisi const array
MIME yang benar dan fungsi yang memakainya, namun selektor fungsi membuang
array tersebut; patch model tidak berubah, lalu regenerasi memakai konstruktor
MediaRecorder pada tugas probe. Selektor sekarang punya opt-in sempit untuk
menjaga seluruh respons asli yang terdiri dari satu helper dan const literal
yang dirujuknya. Tidak memindahkan, menulis ulang, atau menyisipkan initializer.
Call initializer, let/mutable declarations, data yang tidak dipakai, helper
lain dan top-level side effects tetap tidak dipertahankan lewat opsi ini.
26 tes terarah lolos, termasuk provenance/replay dan jalur local/online/router
dengan model stub. Itu membuktikan routing kode, bukan akun provider nyata.
V100 tetap meminta respons baru dari model lokal; tidak memulihkan kode
aplikasi dari reference implementation milik tes.

Sesudah opt-in literal dependency, 213 tes regresi terkait (project parts,
evaluator dan export checks) lolos di Windows dalam 144,86 detik. Seluruh
workflow commit ae833eb—Tests Linux, Secret scan, Windows installer dan
Original harness runtimes—juga telah berhasil. Perubahan selektor berikutnya
memerlukan pemeriksaan CI pada commitnya sendiri.

CI Linux untuk selektor literal commit 568450a berhasil: run 37736874293,
526 tes lolos dalam 122,81 detik. V100 masih gagal setelah 235,5 detik karena
model mengembalikan false ketika semua probe codec menolak. Task/diagnostik
menjelaskan bahwa setelah loop harus throw; jumlah kandidat bukan hasil probe.
V101 meloloskan MIME pada respons pertama model, tanpa patch. Run berhenti
setelah 168,6 detik pada seek: import/export module tidak sesuai script klasik,
kemudian respons terakhir hanya menunggu timer dan tidak melakukan seek.

V102 memisahkan waitForVideoTime(video,target) dari pemanggil seekExportStart.
Kedua helper tetap menghadapi kasus seek/timeout/cleanup yang sama; pemanggil
juga diperiksa bersama worker model aslinya. 28 tes terarah lolos. Diagnostik
shared fields kini berasal dari AST MemberExpression (termasuk bracket string),
bukan substring dalam komentar atau nama berkas app.js/ui.js. Tidak menghapus
prefix module dari sumber model; model harus memperbaiki sumbernya sendiri.

Sesudah pemisahan worker seek dan diagnostik AST, 215 tes regresi terkait
lolos di Windows (112,39 detik). File benchmark v102 masih terpisah di
.local-tools/hasil-uji-web; hasil ini tidak menandai video editor selesai.

V102 gagal setelah 195,8 detik: worker mendeklarasikan ulang parameter video,
kemudian menulis annotation TypeScript dan blok querySelector berulang.
V103 menghilangkan simbol tipe dari deskripsi parameter dan meminta Promise
langsung dari argumen yang sudah ada, tanpa pencarian elemen atau penulisan
ulang sumber oleh evaluator. Kasus seek/timeout/cleanup tetap sama.

V103 tidak digunakan sebagai pembanding seek: edit batas token tidak sengaja
mengenai panel library, sehingga cache panel tidak cocok dan run gagal pada
input berkas setelah 67,3 detik. Batas panel dikembalikan ke 650; hanya worker
seek memakai 450. V104 melanjutkan checkpoint v102 dengan panel asli.

V104 gagal setelah 124,2 detik. Respons model mencoba play dan timer sebagai
pengganti event seek, lalu regenerasi menolak waktu nol dan tidak menjaga
siklus reject/cleanup. V105 membagi job seek menjadi data, pembersihan handle,
sukses, gagal dan pemasangan event, lalu menggabungkannya melalui Promise.
Semua helper tetap ditulis model. Pemeriksaan gabungan tetap menguji seek
sebelum assignment, timeout lima detik, cleanup dan galat assignment asli.
39 tes terarah lolos; fixture/reference penguji tidak masuk prompt atau hasil
aplikasi. CI Linux commit 78ec695 (run 37738491963) berhasil. V105 masih
memerlukan hasil model nyata dan pengujian browser; editor belum dinyatakan
selesai atau layak pakai.

V105 gagal setelah 126,1 detik pada makeSeekJob: timer/onSeeked dibuat sebagai
variabel lokal dan tidak masuk objek hasil; patch pertama tidak berubah,
regenerasi meng-clone argumen dan menulis ulang const. 226 tes regresi terkait
lolos (121,62 detik). V106 memperjelas lima properti objek serta identitas
argumen asli. Pesan penguji menyertakan properti dan nilai aktual, tanpa
memberikan kode solusi. 39 tes terarah tetap lolos.

V106 meloloskan makeSeekJob pada respons pertama model, sumber/hash asli
disimpan pada parts/94.json. Run gagal setelah 117,3 detik pada clearSeekJob:
tidak removeEventListener, mengakses video.seeked dan memakai truthiness untuk
timer sehingga handle nol terlewat. V107 memperjelas kontrak properti job dan
empat langkah cleanup. Tambahan jatah reasoning sudah ada pada jalur patch;
masalah ini tidak dibuktikan sebagai kekurangan token. 39 tes tetap lolos.

V107 meloloskan cleanup, completeSeekJob dan failSeekJob pada respons pertama.
Empat job helper sudah model-authored dengan provenance asli; run gagal
setelah 255,7 detik pada armSeekJob. Model mendeklarasikan ulang parameter,
memperlakukan handle sebagai API dan menaruh assignment di dalam event.
V108 memperjelas urutan langkah langsung versus callback dan bentuk argumen.
Penguji tetap menolak callback/timer yang tidak terpasang, tetapi memeriksa
keberadaannya sebelum mencoba memanggilnya agar galat fixture tidak menutupi
penyebab awal. 40 tes terarah lolos, termasuk regresi diagnostik tersebut.
CI Linux e04dfe2 berhasil: run 37740129877, 539 tes lolos (102,96 detik).

V108 gagal setelah 258,0 detik. Respons awal benar pada listener, timeout dan
assignment, tetapi tidak menyimpan return value setTimeout ke job.timer.
Patch menyalin ulang sumber; regenerasi menduplikasi helper dan terpotong.
V109 memberi diagnostik nilai aktual pada handle/delay. Penguji memakai
handle 0, 37 dan 311 dan menolak nilai hardcode atau handle yang tidak
disimpan. 42 tes terarah lolos. CI Linux 4af6317 berhasil: run 37741033009,
540 tes lolos (98,19 detik). Semua hasil ini tetap belum membuktikan editor
lengkap; ekspor nyata dan UI/browser belum lulus.

V109 gagal setelah 186,6 detik. Respons awal memakai let timerHandle dan
mengembalikannya, tidak menyimpan job.timer. Patch menghapus whitespace saja;
regenerasi mengeksekusi callback completion secara langsung dan terpotong.
Percobaan pembanding video-lfm-current-v1 menggunakan LFM2.5 1.17B Q4 CPU
dengan sampling lfm25 pada harness/checker/recipe yang sama. Dimulai kosong;
tidak memakai checkpoint/sumber Qwen atau mengganti hasil dengan template.
Hasil pembanding ini harus ditunggu, bukan diasumsikan lebih baik.

video-lfm-current-v1 gagal pada Document setelah 11,8 detik: app.js tidak
ditautkan. Prompt dokumen sekarang membedakan tautan eksternal wajib dari
implementasi inline yang dilarang. v2 meloloskan dokumen model tetapi gagal
header setelah 14,9 detik: JSON source berisi deskripsi, bukan HTML.
Fallback generik meminta sumber mentah pada sisa attempt hanya ketika
respons HTML terstruktur tidak berisi tag. Tidak mengubah markup yang sudah
ada menjadi raw atau menurunkan pemeriksaan atribut/kontrol. 16 tes terarah
lolos untuk local/online/router stub dan kasus prose versus markup rusak.
v3 membuktikan fallback menghasilkan markup model asli, tetapi header belum
memuat kontrol wajib; tetap gagal setelah 11,1 detik. 235 tes regresi terkait
lolos (88,80 detik).

Qwen V110 kembali memakai checkpoint Qwen V109, tanpa sumber LFM. Helper arm
memperoleh konteks opt-in berisi implementasi clear/complete/fail yang sudah
ditulis dan lolos oleh model yang sama, agar kontrak handle terlihat dari
pemakaiannya. Ini memakai mekanisme validated_helper_context yang ada;
bukan implementasi reference milik tes atau kode solusi evaluator.

V110 gagal setelah 410,7 detik: respons pertama berupa komentar berulang dan
terpotong; respons berikutnya memakai event sebagai timeout, handle 5000
hardcode dan assignment tanpa catch. Patch terakhir tidak mengubah sumber.
V111 memisahkan registerSeekEvent, scheduleSeekTimeout dan assignSeekTarget;
armSeekJob hanya mengurutkan panggilan ketiganya. Pemeriksaan arm memakai tiga
helper operasi model; Promise worker dan caller menggabungkan seluruh job
helper model aktual melalui behavior_dependencies. 47 tes terarah lolos (7,93
detik), termasuk penolakan callback langsung, handle hardcode, galat assignment
yang tidak ditangani dan urutan timer/listener terbalik. Ini tidak menyatakan
hasil editor telah lulus; hasil model V111 masih harus ditunggu.

V111 gagal setelah 133,4 detik pada registerSeekEvent: callback event benar
tetapi tidak disimpan ke job.onSeeked; patch noop dan regenerasi tetap
kehilangan properti. Pembanding video-deepseek13-current-v1 dimulai kosong
dengan DeepSeek Coder 1.3B Instruct Q5_K_M lokal, sampling greedy, template
chat Instruction/Response yang tersimpan serta pre-tokenizer deepseek-coder
untuk GGUF lama. SHA256 bobot d5dcc2a484498b412b8bf5821b0ef2a7ea2e1984b37d15e14344259068d19a31.
Tidak memakai sumber/checkpoint Qwen atau LFM. Model ini berukuran 1.3B;
bukan menyatakan tepat 1B atau telah menghasilkan editor yang lulus.

CI Linux commit b3b168b berhasil: run 37743871565, 553 tes lolos (102,17
detik). Ini mencakup perubahan fallback HTML dan pemisahan operasi seek;
editor yang dihasilkan tetap harus melewati evaluasi model nyata/browser.

DeepSeek current-v1 gagal setelah 299,5 detik di preview: sumber lengkap
memiliki controls pada video, lalu model mengulang penghapusan span yang sama
empat kali. Patch ditolak secara atomik. Schema penghapusan sekarang membatasi
jumlah edit sesuai jumlah span unik yang memang ada; satu span hanya memberi
ruang satu edit. 15 tes terarah dan 245 tes regresi terkait lolos (116,16 detik),
termasuk penolakan duplikasi pada local/online/router stub.

Pemulihan opt-in failed source kini mencakup HTML kind node yang mempunyai
root_class dan reproduksi span asli tepat. Tetap wajib recipe, bobot, format
chat dan sampling cocok; hasil gagal harus diperiksa lagi, bukan dianggap
lulus. Sumber terpotong, patch, SHA berubah, atau hasil yang tidak dapat
direproduksi ditolak. DeepSeek current-v2 memakai checkpoint valid v1. Kandidat
preview lama tidak dipakai karena kind-nya panel, sementara pemulihan baru
mencakup node. Model menghasilkannya ulang dan meloloskan patch satu penghapusan;
provenance/replay tersimpan pada parts/05.json. CSS masih sedang dikerjakan.

DeepSeek current-v2 selesai dengan kegagalan setelah 406,7 detik pada CSS
mobile .stage. Dokumen, panel dan CSS desktop sampai bagian 41 telah lulus;
editor belum lengkap. current-v3 meloloskan bagian 42–45 melalui patch asli
model: menghapus aturan global, lalu membetulkan urutan library berdasarkan
galat pemeriksaan. Run gagal setelah 167,3 detik pada .viewer-surface karena
teks aturan global identik dengan aturan yang benar di dalam media block.
Patch find ambigu tidak boleh menghapus salinan yang benar.

Penghapusan kini dapat memakai start/end/remove dari posisi teks asli yang
ditemukan parser CSS. Model memilih span global yang ditawarkan; harness tidak
menulis deklarasi pengganti. Penguji menolak span lain, rentang berubah,
duplikasi atau overlap; provenance dapat direplay dengan hash asal dan patch.
28 tes terarah lolos (1,65 detik), termasuk Unicode/CRLF, salinan CSS identik
dan penolakan edit ke blok media pada local/online/router stub. Pembuktian
provider nyata tetap berbeda dari tes stub. current-v4 memakai bobot,
serialization, sampling dan checkpoint DeepSeek yang sama; hasil model nyata
dan ekspor di browser masih harus ditunggu.

251 tes regresi sebelum penambahan edit posisi lolos (160,35 detik). CI Linux
commit c6282e6 berhasil: run 37745943560, 558 tes lolos (124,24 detik).

current-v4 meloloskan .viewer-surface dengan patch posisi yang benar-benar
dikeluarkan DeepSeek (start 0, end 70, span asli), kemudian #preview. Run gagal
setelah 81 detik pada .topbar: patch nilai justru mengganti flex-wrap menjadi
flex-direction. Seluruh sumber/patch gagal tetap disimpan; tidak diperbaiki
secara manual. 258 tes regresi terkait lolos (98,58 detik).

Perbaikan nilai CSS sekarang memakai konteks hanya deklarasi asli yang gagal,
jika semua galat memang menyangkut nilai properti yang sudah ada. Nomor baris
asli tetap dipakai; respons tidak boleh mengganti nama properti, menambah
deklarasi atau menyentuh blok lain. Galat struktur/properti yang hilang tetap
memakai editor sumber biasa. 24 tes CSS/posisi lolos (1,02 detik) setelah
pembatasan satu deklarasi per baris. current-v5 menguji mekanisme ini melalui
model lokal yang sama. Editor dan ekspor nyata belum dinyatakan lulus.

current-v5 gagal setelah 34,8 detik: model menyalin nilai lama dan menambahkan
newline pada setiap pengganti deklarasi; patch ditolak. 265 tes terkait lolos
(85,49 detik). Konteks generasi CSS mobile kini menyebut query dan scope sejak
awal, serta meminta deklarasi yang diminta hanya di dalam media block.
Harness tidak menyediakan kode CSS lengkap. 27 tes terarah lolos (1,63 detik),
termasuk pemeriksaan prompt local/online/router tanpa source evaluator.
current-v6 sedang menguji perubahan itu pada model DeepSeek yang sama.

current-v6 meloloskan header mobile pada respons pertama dan seluruh HTML/CSS
sampai bagian 50. App state dan DOM references juga lulus, tetapi run gagal
setelah 195,1 detik pada normalizeSeconds: respons memanggil isInfinity yang
tidak ada, lalu regenerasi mengembalikan 0 untuk bilangan positif. Ini bukan
hasil editor selesai. Tampilan draft diuji di browser pada 1280×720 dan
390×844: tiga panel desktop, preview lebih dulu di mobile, tanpa overflow
horizontal (scrollWidth 375 pada viewport 390). Kontrol belum diuji karena
inisialisasi aplikasi belum selesai.

268 tes regresi terkait commit 46a07d9 lolos (105,63 detik); scan seluruh
riwayat Git menemukan 0 rahasia. Qwen V112 kembali ke checkpoint Qwen V111,
tanpa kode DeepSeek/LFM, bobot Qwen0.8B Q8 dan reasoning 256 tetap sama.
Kontrak registerSeekEvent menegaskan bahwa onSeeked adalah properti input job
yang memang harus diubah, dan memberikan konteks implementasi clearSeekJob
yang sebelumnya sudah ditulis model agar callback yang sama dapat dilepas.
29 tes seek/recipe/konteks lolos (12,42 detik). Pemeriksaan event, handle,
timeout, galat dan identitas callback tetap dipakai; ekspor browser belum lulus.

Qwen V112 selesai dengan kegagalan setelah 127,9 detik. Respons pertama
memakai export dan assignment ke dirinya sendiri; regenerasi menganggap
onSeeked sudah berisi callback lalu melempar galat. V113 memisahkan pembuatan
callback, penyimpanannya pada job dan pemasangan listener menjadi tiga helper
parameter-only. registerSeekEvent hanya menyusun store lalu listen. Seluruh
dependensi helper model disertakan secara eksplisit pada pemeriksaan register,
arm, Promise worker dan caller. Pemeriksaan gabungan asli tidak dikurangi.
56 tes ekspor terarah lolos (9,04 detik), termasuk penolakan callback yang
dipanggil terlalu cepat, job salinan, hasil factory yang tidak disimpan,
event keliru, callback pengganti dan urutan store/listen terbalik. Tidak ada
source reference penguji yang masuk recipe/prompt/model runtime.

CI Linux commit 46a07d9 berhasil: run 37748596181, 581 tes lolos (97,04 detik).

V113 meloloskan makeSeekCallback dan storeSeekCallback pada respons pertama
model. Raw source dan hash disimpan pada parts/98.json serta parts/99.json;
keduanya sumber Qwen0.8B, bukan source fixture. 277 tes regresi terkait lolos
(103,07 detik). Listener dan pemeriksaan gabungan masih sedang dikerjakan.

V113 kemudian gagal setelah 141,7 detik: listener membungkus onSeeked dengan
arrow function baru, sehingga identitas handler berubah; patch noop dan
regenerasi memakai import. Diagnostik sekarang membedakan event/count dari
identitas argumen callback. Parser AST menawarkan hanya pasangan span wrapper
dan referensi fungsi yang keduanya sudah ada di sumber asli model. Model tetap
mengeluarkan patch; source tidak dieksekusi ketika mencari span, dan pasangan
yang mengubah argumen lain atau memanggil callback langsung ditolak. 43 tes
callback/seek/recipe lolos (5,81 detik). Percobaan penulisan tes sebelumnya
gagal karena encoding Windows; berkas dipulihkan dari commit terakhir dan
pemeriksaan diulang penuh, bukan menghitung run dengan tes yang terpotong.

V114 menguji pemulihan exact failed source bagian 100 dari V113, dengan bobot,
recipe, sampling dan format Qwen yang sama. Kandidat tetap diperiksa ulang dan
belum dianggap lulus sebelum patch serta seluruh pemeriksaan berhasil.

V114 membuktikan perbaikan listener pada model nyata: Qwen mengeluarkan patch
yang mengganti span arrow wrapper asli dengan span job.onSeeked asli. Bagian
100 lulus pemeriksaan identitas callback; registerSeekEvent bagian 101 juga
lulus sebelum proses lanjut ke timer. 284 tes regresi terkait lolos (104,77
detik), termasuk validasi pasangan span pada local/online/router dan replay
hash sumber/patch. Sumber model lengkap serta ekspor browser masih ditunggu.
CI Linux commit 47a2983 berhasil: run 37749798772, 590 tes lolos (99,06 detik).

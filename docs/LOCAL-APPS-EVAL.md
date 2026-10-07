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

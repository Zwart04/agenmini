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

Browser nyata mengunggah PNG valid 32×16 ke converter Qwen (`a2ed35ac`).
Aplikasi menampilkan “File tidak valid” dan menonaktifkan tombol konversi.
Kode juga menyalin file asli, tanpa proses canvas/resize yang diminta.
Ini **gagal**, meskipun pemeriksaan sintaks dan ZIP sebelumnya berhasil.

Browser nyata mengunggah teks “apel apel jeruk café 日本語” ke editor LFM
(`cc96a2e3`) lalu menekan Save. Console mengembalikan
`TypeError: file.readAsText is not a function`. Replace-all, kontrol pencarian
dan hitungan kata yang diminta belum lengkap. Ini **gagal**.

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

Laporan, draft dan kode tetap dalam direktori temp yang dicetak evaluator.
Uji browser independen tetap diperlukan. Model 0.8B/1.2B belum terbukti andal
untuk kedua tugas ini; jangan menyamakan harness dengan training bobot atau
kemampuan model besar.

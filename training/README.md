# Membuat model kecil lebih berguna

Self-improve di Agen Mini mengembangkan prosedur dan konteks; bobot model tetap sama. Model 0.8–2B bisa lebih andal pada tugas tertentu melalui alat nyata, pencarian, verifikasi, dan fine-tuning spesifik. Tidak ada metode yang menjamin kemampuan umum setara model frontier pada semua tugas. Skill atau memori tidak menambah parameter model.

## Yang berjalan di Agen Mini

Profil kosong tidak memasang skill, ingatan, MCP atau tim tambahan, dan tidak disemai lagi pada update. Harness minimal memakai permintaan pengguna dan alat yang ditugaskan tanpa pengenal niat/delegasi otomatis. Akses penuh menghilangkan tinjauan tindakan di lingkup alat, tetapi tidak memberi kredensial, menghilangkan batas folder atau melampaui kuota/konteks provider.

Profil bawaan memakai tim spesialis dan prosedur. Untuk lokal, daftar alat yang panjang diperkecil; `find_tools` membuka definisi lain sesuai tugas tanpa memperluas izin bot. Model membaca hasil eksekusi dan galat, bukan jawaban contoh yang dianggap sukses.

Pekerjaan dengan bukti alat menghasilkan kandidat skill. Satu review AI singkat saat idle dapat menyarankan langkah yang lebih umum; bukti tetap disimpan dan usulan tidak dianggap sudah diuji. Mode Tinjau membutuhkan persetujuan; mode Setelah Sesuai memakai penilaian pemilik. Revisi skill menyimpan versi lama. Penilaian bolak-balik tidak menambah skor palsu. Pelajaran koreksi berasal dari pengguna, bukan tebakan model.

## Training bobot: jalankan terpisah

1. Tetapkan tugas sempit, misalnya pemakaian alat berkas, jawaban Indonesia atau perbaikan proyek Python. Rekam baseline model asli dengan `tests/evaluate_local.py` pada server llama.cpp yang benar-benar berjalan. Catat model/hash, quantization, hardware, waktu, hasil dan galat. Script tersebut menguji layanan nyata, bukan fixture pytest.
2. Kumpulkan jawaban berkualitas yang dinilai Sesuai, atau contoh dari teacher yang Anda berhak gunakan. Jangan menyalin reasoning privat. Tinjau lisensi model/dataset dan ketentuan provider. Data teacher yang salah harus ditolak berdasarkan tes/sumber, bukan dipercaya karena ukuran modelnya.
3. Pengaturan > Skill > Ekspor menghasilkan JSONL privat pasangan jawaban user/assistant; bukan data tool-call lengkap. Rahasia yang dikenali dan hasil gagal tidak diekspor. Penyaring otomatis bukan jaminan bebas data pribadi: periksa sendiri dan hapus data yang tidak boleh dipakai. Ekspor tidak dikirim ke GitHub/provider.
4. Di mesin training, `python training/prepare_dataset.py agenmini-confirmed.jsonl dataset-baru` memvalidasi, deduplikasi dan memisahkan pertanyaan train/validation. Sepuluh contoh hanya cukup untuk smoke experiment; gunakan contoh representatif yang beragam untuk eksperimen bermakna. Simpan benchmark acceptance terpisah dari keduanya.
5. Gunakan [TRL SFTTrainer](https://huggingface.co/docs/trl/en/sft_trainer) dan [PEFT LoRA/QLoRA](https://huggingface.co/docs/peft/en/developer_guides/quantization), atau notebook resmi [Unsloth](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide) yang mendukung arsitektur base pilihan. Pasangan conversational JSONL memakai chat template base yang sesuai. Jalankan di GPU yang memadai; kebutuhan VRAM tergantung arsitektur, sequence length, batch dan precision. Tidak memasang dependency ML atau menyalakan training pada VPS Agen Mini.
6. Training tool-calling membutuhkan dataset khusus dengan seluruh tools schema, argumen JSON yang valid, hasil alat lengkap dan pesan assistant sesudahnya. Trace UI yang terpotong **jangan** dijadikan label training. SFT jawaban saja belum membuktikan kemampuan memakai alat.
7. Bandingkan adapter dengan base pada acceptance set yang belum terlihat: memilih alat, argumen, mengoreksi galat, menolak klaim hasil palsu, output kode yang benar-benar lolos tes. Jalankan tes model sebelum dan sesudah quantization. Jangan mengganti default bila terjadi regresi. Simpan base sebagai rollback.
8. Merge/export hanya dengan converter yang mendukung arsitektur. Gunakan GGUF teks Q4 yang sesuai lalu import melalui Koneksi > Model lokal, atau host sebagai API `/v1`. API provider tertutup tidak bisa dilatih oleh Agen Mini; gunakan harness/skill/memori atau fine-tuning resmi provider jika tersedia.

## Sumber riset

- [Hermes skills](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md): blank slate opt-out dan progressive disclosure; ini inspirasi desain, bukan integrasi/fork Hermes.
- [Hermes self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution): optimasi prompt/skill dengan DSPy/GEPA dan evaluasi. Tidak dibundel agar runtime tetap ringan.
- [Qwen3.5-0.8B model card](https://huggingface.co/Qwen/Qwen3.5-0.8B): tujuan mencakup prototyping dan task-specific fine-tuning; parameter kecil tetap membatasi kemampuan umum.
- [Diskusi komunitas tentang self-improve](https://www.reddit.com/r/hermesagent/comments/1upvfe7/hermes_agents_selfimprovement_does_it_actually/): pengalaman pengguna, bukan bukti benchmark atau resep training. Implementasi di atas mengacu dokumentasi primer.

Belum ada bobot baru yang dilatih atau benchmark frontier yang terbukti. Nama model API harus berasal dari daftar provider aktual; Agen Mini tidak menganggap alias “Astra”, “Opus” atau “Fable” otomatis tersedia.

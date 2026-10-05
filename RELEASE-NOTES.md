# Agen Mini 0.8.1

Notifikasi custom berada di tengah viewport, termasuk ketika memakai Popover API. Lebar dan teks panjang dibatasi agar pesan tidak terpotong di sisi layar.

Instalasi baru dimulai dengan Orchestrator. Template spesialis dapat dipilih pada setup atau Workspace → Tim bot → Template bot. Bot milik pengguna tidak ditimpa; template bot terpisah dari skill, ingatan dan MCP. Orchestrator dapat diedit tetapi tidak dihapus.

Setup web menyediakan sandi baru opsional dengan konfirmasi; sesi lama dibatalkan setelah perubahan. Pemasang VPS menawarkan sandi otomatis/sendiri, swap 0/2/4/8 GB dan resource bawaan atau CLI asli. Rekomendasi swap memakai RAM fisik; swap yang sudah ada dipertahankan. Swap bukan tambahan RAM fisik atau cara memperbesar batas container.

Saat pemasangan harness ditolak oleh batas container, tombol Siapkan RAM container & coba lagi meminta supervisor menaikkan batas menjadi 2 GB dan melanjutkan pemasangan setelah restart saat senggang. Memerlukan minimal 2,5 GB RAM fisik; tidak mengunduh bobot model. Batas lebih besar dan data/model/kredensial lama dipertahankan. Aplikasi tidak mendapat Docker socket atau akses root; permintaan host memakai pilihan tetap.

Linux diuji melalui GitHub Actions dengan uji aplikasi dan perintah host yang dimock dalam container disposable. Tidak mengakses VPS pengguna. Pengujian tidak memakai akun model pengguna atau membuktikan swapon nyata pada VPS tersebut.

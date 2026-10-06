# Media Monitor KPw BI DKI Jakarta

Dashboard pemantauan berita untuk kehumasan KPw Bank Indonesia Provinsi DKI Jakarta. Berita yang tampil berasal dari RSS media dan Google News yang berhasil diurai ke URL penerbit. Sumber yang gagal ditulis sebagai status, tidak diganti artikel karangan.

## Menjalankan

Perlu Python 3.9+ dan Node.js 20+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Di terminal lain:

```bash
cd frontend
npm install
npm run dev
```

Buka http://127.0.0.1:5173. Dokumentasi API ada di http://127.0.0.1:8000/docs.

Untuk dibuka orang lain, bangun image dari `Dockerfile` lalu jalankan di layanan yang menyediakan URL publik (misalnya Render, memakai `render.yaml`). Layanan harus membuka port `PORT`. Data tersimpan di SQLite pada disk layanan itu dan diperbarui otomatis setiap 2 jam.

Atau dari akar proyek: `bash scripts/dev.sh`.

## Akun demo

| Pengguna | Sandi | Peran |
| --- | --- | --- |
| analis | analis123 | koreksi label dan status |
| pimpinan | pimpinan123 | hanya melihat |
| admin | admin123 | kata kunci, bobot, aturan, pengambilan data |

Sandi ini hanya untuk latihan di komputer sendiri. Jangan membukanya ke jaringan kantor sebelum diganti.

## Isi layar

- **Ikhtisar**: mention, sentimen, jangkauan, isu kritis, tren, upside dan downside.
- **Sentimen**: sebaran kategori, alasan klasifikasi, uji teks, koreksi manusia.
- **Isu & Topik**: awan kata, tagar, entitas, dan linimasa isu.
- **Radar Kebijakan**: matriks dampak lawan kecepatan, plus aspirasi dan kritik per kebijakan.
- **KPw DKI**: mention lokal, peta skematik, performa kanal resmi.
- **Sumber**: peringkat media dan akun. Akun mencurigakan ditandai "perlu diverifikasi".
- **Explorer**: tabel, filter, status penanganan, ekspor CSV.
- **Alert**: aturan dan notifikasi di dalam dashboard.
- **Laporan**: ringkasan, Excel, salindia PPTX, dan cetak PDF.
- **Kata Kunci** dan **Pengaturan**: kamus, boolean, dan bobot risiko.

Filter tanggal, platform, dan kategori di bagian atas berlaku di semua halaman.

## Dokumen

- [Arsitektur dan alur data](docs/ARSITEKTUR.md)
- [Skema PostgreSQL](docs/SKEMA.sql)
- [Klasifikasi dan skor risiko](docs/KLASIFIKASI.md)
- [Roadmap](docs/ROADMAP.md)

## Sumber data

Salin `backend/.env.example` menjadi `backend/.env` bila ada kunci API. Penjadwal mengambil data baru setiap 2 jam (WIB). Admin dapat menekan **Perbarui sekarang**.

Yang dipakai tanpa kunci:

- RSS langsung: Detik Finance, Antara, CNN Indonesia, Tempo, Liputan6, Bloomberg Technoz.
- Google News RSS. Tautan `news.google.com` diurai ke URL penerbit sebelum disimpan. Kalau uraian gagal, item dibuang.
- Pencarian Google News untuk unggahan Instagram, TikTok, X, dan Facebook. Permalink yang tidak terurai dibuang. Threads tidak punya feed publik.

Kanal dan situs milik Bank Indonesia tidak masuk. Daftar blokir (domain, akun, nama kanal) diubah Admin di halaman Kata kunci. Berita atau unggahan pihak luar yang mengutip pernyataan BI tetap tampil dengan label Mengutip BI. Kanal YouTube resmi BI tidak diambil.

Yang butuh akun atau persetujuan, dan saat kosong tampil **sumber tidak tersedia**:

- NewsAPI: paket produksi berbayar.
- YouTube Data API: proyek Google Cloud.
- X API: berbayar.
- Instagram, Facebook, Threads: Meta Graph API dan app review.
- TikTok Research atau Display API: persetujuan TikTok.
- Vendor social listening (Brand24, Meltwater, Brandwatch, Talkwalker) belum disambungkan. Tidak ada unggahan pengganti.

GDELT dipakai bila API-nya menjawab. Bila menolak, status konektor gagal dan tidak ada artikel isian.

Cuplikan dibatasi dari deskripsi feed. Jangkauan dan engagement tidak diisi angka perkiraan.

## Batas versi ini

Analisis otomatis dapat keliru. Hasil wajib dibaca manusia, lewat tautan sumber asli, sebelum menjadi pernyataan resmi atau bahan keputusan kebijakan.

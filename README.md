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

Atau dari akar proyek: `bash scripts/dev.sh`.

## Deploy publik (GitHub + Render)

Link publik yang **tetap** (tidak berganti seperti tunnel Codespace) memakai Render yang terhubung ke repo GitHub. Setiap `git push` ke `main` memicu build ulang dari `Dockerfile`.

### Satu kali: hubungkan Render ke GitHub

1. Buka [dashboard.render.com](https://dashboard.render.com) dan masuk dengan akun **GitHub** yang punya repo ini.
2. **New** → **Blueprint** → pilih `emailnyaaes-hub/media-monitor-kpw-dki` (branch `main`).
3. Apply blueprint dari `render.yaml`. Tunggu build Docker selesai (beberapa menit).
4. Buka URL layanan, bentuknya `https://media-monitor-kpw-dki.onrender.com` (atau nama yang dipilih di dashboard).

Detail verifikasi: [docs/DEPLOY.md](docs/DEPLOY.md).

### Sesudah itu

- Update kode → `git push origin main` → Render deploy otomatis.
- Tutup Cursor **tidak** mematikan layanan.
- Paket **free**: setelah idle ~15 menit app bisa sleep; buka pertama bisa 30–60 detik. URL tetap sama.
- Data SQLite di free plan tidak punya disk permanen: hilang saat redeploy, lalu diisi lagi oleh penjadwal (setiap 2 jam WIB) atau tombol **Perbarui sekarang**.

Jangan pakai Codespace + `trycloudflare.com` untuk akses publik harian; itu sementara dan URL-nya berganti.

## Akun

| Pengguna | Sandi | Peran |
| --- | --- | --- |
| admin | admin123 | akses penuh: koreksi label, kata kunci, bobot, aturan, pengambilan data |

Sandi ini hanya untuk latihan. Ganti sebelum dibuka ke jaringan kantor.

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

- [Deploy publik (GitHub + Render)](docs/DEPLOY.md)
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

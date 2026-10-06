# Roadmap

## Sekarang (MVP)

Dashboard berjalan dengan berita dari RSS dan Google News. Klasifikasi memakai leksikon, koreksi manusia, radar kebijakan, alert di dalam aplikasi, serta ekspor CSV, Excel, dan cetak PDF.

## Tahap 2 — data sungguhan

- Pasang NewsAPI atau vendor berlisensi, GDELT, dan RSS media yang izinnya jelas pada `backend/app/connectors`.
- Pasang X API, YouTube Data API, dan Meta Graph API hanya untuk akun dan konten publik yang terms-nya mengizinkan.
- Jadwalkan `python -m app.jobs` setiap 15 menit.
- Pindah ke PostgreSQL dengan `docs/SKEMA.sql`. Tambah OpenSearch bila pencarian teks sudah terasa lambat.
- Simpan cuplikan, bukan salinan penuh yang melampaui lisensi sumber.

## Tahap 3 — model bahasa

- Ganti isi `analyze()` dengan IndoBERT untuk sentimen, tetap di antarmuka hasil yang sama.
- Pakai prompt ringkasan isu ke LLM internal bila nanti tersedia. Ringkasan saat ini hanya menyusun judul dan tautan yang benar-benar terkumpul.
- Latih ulang dari tabel audit. Jangan campur data latihan dengan percakapan privat.
- Uji sarkasme dan bahasa gaul pada sampel yang sudah dikoreksi analis sebelum model dipakai luas.

## Tahap 4 — peringatan dan laporan

- Kirim alert Info, Waspada, dan Kritis ke email kantor. WhatsApp atau Telegram hanya setelah ada gateway resmi.
- Rapikan template PPTX sesuai format rapat pimpinan. Versi sekarang sudah mengunduh salindia ringkas.
- Topic modeling (misalnya BERTopic) untuk mengusulkan klaster, dengan analis yang tetap mengesahkan nama isu.

## Tahap 5 — tata kelola

- Ganti login demo dengan akun kantor dan peran yang sudah ada.
- Catat akses baca pada data sensitif, bukan hanya perubahan label.
- Tetapkan masa simpan mention dan prosedur penghapusan sesuai UU PDP.
- Tinjau berkala istilah eksklusi agar pemantauan tidak melebar ke kehidupan pribadi.

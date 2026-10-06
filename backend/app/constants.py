"""Kamus nilai yang dipakai bersama API, basis data, dan antarmuka.

Ubah daftar ini bila unit ingin menambah kategori atau platform.
Jangan mengubah ejaan nilai yang sudah tersimpan di data lama
(misalnya "dieskalasi") tanpa migrasi.
"""

from __future__ import annotations

# Zona waktu operasional kantor. Timestamp disimpan tanpa tz, dalam WIB.
TIMEZONE_NAME = "Asia/Jakarta"

CATEGORIES = [
    "Kebijakan Moneter",
    "Sistem Pembayaran",
    "Rupiah/Kurs",
    "Inflasi",
    "Perbankan/Kredit",
    "Pengedaran Uang",
    "Reputasi/Kelembagaan",
    "Hoaks/Penipuan",
    "Kegiatan KPw DKI",
    "Ekonomi Jakarta",
    "Lainnya",
]

# Kode internal -> label yang tampil di UI.
PLATFORMS = [
    ("berita", "Berita online"),
    ("x", "X (Twitter)"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
    ("facebook", "Facebook"),
    ("threads", "Threads"),
    ("forum", "Forum"),
]

PLATFORM_LABELS = dict(PLATFORMS)

SENTIMENTS = ["positif", "netral", "negatif"]
STANCES = ["upside", "netral", "downside"]
IMPACT_LEVELS = ["rendah", "sedang", "tinggi"]

# Alur penanganan isu di meja analis.
STATUSES = ["baru", "ditinjau", "dieskalasi", "ditangani", "selesai"]
STATUS_LABELS = {
    "baru": "Baru",
    "ditinjau": "Ditinjau",
    "dieskalasi": "Dieskalasi",
    "ditangani": "Ditangani",
    "selesai": "Selesai",
}

SEVERITIES = ["info", "waspada", "kritis"]
SEVERITY_LABELS = {
    "info": "Info",
    "waspada": "Waspada",
    "kritis": "Kritis",
}

ROLES = ["admin", "analis", "pimpinan"]
ROLE_LABELS = {
    "admin": "Admin",
    "analis": "Analis",
    "pimpinan": "Pimpinan",
}

JAKARTA_AREAS = [
    "Jakarta Pusat",
    "Jakarta Utara",
    "Jakarta Barat",
    "Jakarta Selatan",
    "Jakarta Timur",
    "Kepulauan Seribu",
]

# Skor sumbu Y pada matriks prioritas. Garis pemisah dampak ada di angka 50.
IMPACT_SCORE = {"rendah": 30, "sedang": 62, "tinggi": 88}

DISCLAIMER = (
    "Analisis sentimen, skor risiko, dan rekomendasi pada sistem ini dihasilkan "
    "dengan bantuan aturan otomatis dan dapat dilengkapi model AI. Hasil bersifat "
    "pendukung, dapat keliru, dan wajib diverifikasi manusia sebelum dipakai untuk "
    "keputusan, pernyataan resmi, atau perumusan kebijakan."
)

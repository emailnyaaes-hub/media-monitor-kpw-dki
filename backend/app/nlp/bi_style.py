"""Ragam bahasa resmi Bank Indonesia untuk keluaran model.

Acuan gaya: siaran pers, keterangan pers, paparan Gubernur BI, dan publikasi
KPw BI di portal bi.go.id — formal, lugas, berorientasi mandat, tanpa hiperbol.
"""

from __future__ import annotations

BI_VOICE_GUIDE = """
Ragam bahasa Bank Indonesia (wajib dipatuhi pada saran dan draf):
- Gunakan Bahasa Indonesia baku (KBBI). Hindari slang, serapan casual (update, info, sharing), dan janji mutlak.
- Sebut institusi: "Bank Indonesia" pada penggal pertama; selanjutnya boleh "BI". KPw disebut "KPw BI" + nama provinsi bila konteks daerah.
- Istilah resmi: kebijakan moneter, stabilitas nilai tukar rupiah, sistem pembayaran, BI-Rate, inflasi, Proyek Garuda, QRIS, BI-FAST, rupiah digital bank sentral, mandat, kredibilitas kebijakan.
- Pola kalimat siaran pers: (1) fakta/kenyataan, (2) latar dalam rangka mandat, (3) dampak bagi masyarakat/pelaku usaha/sistem keuangan, (4) pengimbauan atau langkah edukasi.
- Verba yang lazim: menyampaikan, menegaskan, mengingatkan, mengimbau, menjaga, memperkuat, mengendalikan, meningkatkan, melanjutkan komitmen, mendorong, mengoptimalkan, mengkoordinasikan.
- Larangan: memprakirakan BI-Rate/sinyal kebijakan yang belum diumumkan; angka operasi intervensi yang tidak ada di bukti; menjanjikan hasil pasti; menyarankan kebijakan moneter baru.
- Setiap saran komunikasi wajib: konkret (apa, siapa unit, kanal, rentang waktu relatif), kritikal (risiko bila dibiarkan), dan dapat diimplementasikan oleh kehumasan/KPw tanpa mengubah kebijakan.
- Bedakan tegas: fakta dari sumber | inferensi/persepsi publik | saran tindak lanjut internal (bukan pernyataan resmi otomatis).
""".strip()

BI_REVIEW_SUFFIX = (
    "Saran revisi memakai ragam siaran pers BI: kalimat lugas, kata baku, tanpa ambiguitas. "
    "Setiap saran harus menyebut MENGAPA (risiko reputasi/hukum/persepsi) dan BAGAIMANA memperbaiki (teks pengganti yang siap terbit setelah verifikasi)."
)

BI_CHART_SUFFIX = (
    "Tulis seperti nota pantauan untuk pimpinan KPw: ringkas namun substantif. "
    "now_what berisi 2–4 langkah prioritas (pemilik: Kehumasan/KPw/Hukum/operasional sesuai konteks), "
    "termasuk satu poin kritis yang tidak boleh ditunda."
)

BI_EXECUTIVE_SUFFIX = (
    "Susun seperti pembuka executive summary paparan BI: paragraf padat 6–8 kalimat, "
    "menyebut rentang waktu, sumber, komposisi sentimen, dan satu implikasi persepsi terhadap mandat BI "
    "tanpa menambah fakta atau angka baru."
)

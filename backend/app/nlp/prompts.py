"""Prompt yang dipakai bila tim mengganti modul leksikon dengan LLM.

Fungsi `analyze()` di classifier.py adalah implementasi MVP.
Pada produksi, kirim prompt ini bersama teks ke model bahasa Indonesia
(IndoBERT untuk klasifikasi, atau LLM untuk alasan dan ringkasan).
Simpan keluaran model pada kolom yang sama agar UI tidak perlu diubah.
"""

from __future__ import annotations

CLASSIFY_PROMPT = """
Anda adalah analis media Bank Indonesia. Tugas Anda hanya mengklasifikasikan
satu konten publik (berita atau unggahan) tentang Bank Indonesia atau KPw BI
Provinsi DKI Jakarta. Jangan membuat fakta baru. Jika teks ambigu, pilih netral
dan turunkan confidence.

Kembalikan JSON saja dengan skema:
{
  "sentiment": "positif" | "netral" | "negatif",
  "sentiment_score": angka dari -1 sampai 1,
  "stance": "upside" | "netral" | "downside",
  "confidence": angka dari 0 sampai 1,
  "category": salah satu kategori resmi,
  "policy_tags": daftar kebijakan yang tersentuh,
  "rationale": satu atau dua kalimat bahasa Indonesia, menyebut bukti kata dalam teks,
  "sarcasm": true/false
}

Aturan stance:
- upside: peluang, apresiasi, adopsi kebijakan, klarifikasi yang meredakan, kegiatan yang membangun kepercayaan.
- downside: kritik tajam, risiko reputasi, hoaks, penipuan, gangguan layanan, tekanan yang dapat mengubah persepsi kebijakan.
- netral: laporan faktual tanpa nada yang jelas, atau pro-kontra yang seimbang.

Perhatikan bahasa gaul, singkatan (gak, yg, bgt, anjlok), dan sarkasme.
"bukan hoaks" atau klarifikasi resmi tidak otomatis menjadi downside.
Jangan menyebut nama individu privat. Jangan memberi perintah kebijakan;
rekomendasi komunikasi dibuat modul lain.

Kategori resmi:
Kebijakan Moneter, Sistem Pembayaran, Rupiah/Kurs, Inflasi, Perbankan/Kredit,
Pengedaran Uang, Reputasi/Kelembagaan, Hoaks/Penipuan, Kegiatan KPw DKI,
Ekonomi Jakarta, Lainnya.

Teks:
\"\"\"{text}\"\"\"
""".strip()


SUMMARY_PROMPT = """
Anda menyusun ringkasan isu untuk rapat kehumasan KPw BI DKI Jakarta.
Gunakan hanya cuplikan yang diberikan. Tulis bahasa Indonesia yang ringkas.

Struktur:
1. Apa yang terjadi (2-3 kalimat).
2. Siapa yang bicara (media, akun publik, tokoh dalam kapasitas publik).
3. Sentimen dominan dan pecahannya.
4. Potensi dampak pada persepsi publik atau ruang kebijakan BI. Ini bacaan risiko, bukan keputusan.
5. Rekomendasi respons komunikasi (klarifikasi, kanal, kecepatan). Tandai sebagai saran, bukan instruksi kebijakan.

Jika bukti kurang, tulis "belum cukup bukti".
Jangan mengarang angka yang tidak ada di cuplikan.

Isu: {title}
Cuplikan:
\"\"\"{snippets}\"\"\"
""".strip()

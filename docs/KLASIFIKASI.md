# Klasifikasi upside / downside dan skor risiko

## Stance

- **Upside**: peluang, apresiasi, adopsi yang berjalan, atau kegiatan yang membangun kepercayaan.
- **Netral**: laporan yang berimbang atau belum menunjukkan sikap.
- **Downside**: kritik yang menekan reputasi, hoaks, penipuan, gangguan layanan, atau narasi yang dapat mengubah persepsi kebijakan.

Sentimen (positif, netral, negatif) adalah nada bahasa. Stance adalah arti bagi kehumasan. Keduanya bisa searah, tetapi koreksi analis boleh memisahkannya.

## Mesin MVP

Berkas `backend/app/nlp/__init__.py`:

1. Menormalkan singkatan: gak, yg, bgt, nyungsep, dan sejenisnya.
2. Menghitung kata positif dan negatif. Kata "tidak" atau "bukan" tepat sebelum sebuah kata membalik arti kata itu. Karena itu "bukan hoaks" tidak dihitung sebagai hoaks.
3. Jika ada isyarat sarkasme ("makasih ya", "mantap sekali") bersama kata jatuh atau gagal, nada dibalik dan keyakinan diturunkan.
4. Subkategori dipilih dari kelompok istilah: hoaks, KPw, Jakarta, sistem pembayaran, kurs, inflasi, moneter, kredit, uang, reputasi.
5. Alasan singkat disusun dari kata yang ditemukan, lalu disimpan di kolom `rationale`.

Koreksi manusia mengubah label, menaikkan keyakinan menjadi 1, menandai `human_corrected`, dan menulis jejak audit. Kumpulan koreksi ini yang nanti menjadi data latih. Pengambilan ulang tidak menimpa baris yang sudah dikoreksi manusia.

## Prompt LLM

Teks lengkap ada di `backend/app/nlp/prompts.py` dan ditampilkan di layar Pengaturan. Ringkasnya, model hanya boleh mengembalikan JSON dengan sentiment, skor, stance, keyakinan, kategori, tag kebijakan, alasan, dan tanda sarkasme. Model tidak boleh mengarang fakta atau memberi instruksi kebijakan.

## Skor relevansi kebijakan

Kelompok istilah di `backend/app/nlp/risk.py` (BI-Rate, nilai tukar, QRIS, BI-FAST, rupiah digital, dan seterusnya). Semakin banyak kelompok yang tersentuh, semakin tinggi skor 0–100.

## Skor risiko reputasi

Komponen, dengan bobot bawaan yang jumlahnya 1,00:

| Komponen | Bobot | Arti |
| --- | --- | --- |
| Sentimen | 0,30 | Downside memberi nilai tertinggi |
| Jangkauan | 0,20 | Skala logaritmik agar satu unggahan viral tidak menelan seluruh skor |
| Kecepatan | 0,20 | Kecepatan sebar isu, 0–100 |
| Sumber | 0,15 | Media arus utama memperbesar risiko bila nadanya negatif, dan menekan risiko bila nadanya positif |
| Tokoh | 0,15 | Keterlibatan tokoh publik pada nada negatif |

Setelah dijumlah, upside dikalikan 0,45 dan netral dikalikan 0,72. Berita baik yang ramai tetap tercatat, tetapi tidak diperlakukan sebagai krisis. Hasil dijepit pada 0–100.

Bobot dapat diubah di layar Pengaturan. Jumlahnya harus dekat dengan 1,00. Skor yang sudah tersimpan tidak dihitung ulang otomatis.

## Ambang baca

- 75 ke atas dan stance downside: isu dapat ditandai kritis.
- 55 ke atas: pantau lebih rapat.
- Di bawah itu: pantau rutin, kecuali kecepatan sebarnya tinggi.

Matriks prioritas memotong dampak dan kecepatan pada angka 50:

- Dampak tinggi dan cepat: Prioritas utama
- Dampak tinggi dan lambat: Rencanakan
- Dampak rendah dan cepat: Pantau ketat
- Dampak rendah dan lambat: Pantau rutin

Kuadran memberi urutan perhatian. Warna tetap membedakan peluang dan risiko. Keduanya bukan keputusan.

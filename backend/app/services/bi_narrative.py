"""Template narasi BI untuk saran DSS dan ringkasan (tanpa LLM)."""

from __future__ import annotations


def wrap_recommendation(action: str, channel: str, pack: dict, category: str, urgency: str) -> str:
    if not action or action.startswith("Data belum"):
        return action
    window = "24 jam" if urgency in {"segera", "tinggi"} else "72 jam"
    return (
        f"Dalam rangka menjaga kredibilitas kebijakan, Bank Indonesia disarankan (setelah verifikasi): {action} "
        f"Melalui {channel or 'kanal resmi'}; koordinasi Kehumasan/KPw BI DKI Jakarta. "
        f"KRITIS: {pack['downside']} konten downside pada {pack['count']} sumber — respons dalam {window} "
        f"bila media tier-1 ({pack['tier1']}) ikut membawa narasi. "
        f"Kategori: {category}. Bukan keputusan kebijakan moneter."
    )


def enhance_draft_points(draft: str, pack: dict, channel: str, category: str) -> str:
    lines = [draft] if draft else []
    lines.extend([
        "",
        "Poin kritis:",
        f"• {pack['downside']} dari {pack['count']} konten bernada downside; kredibilitas kanal resmi terancam bila dibiarkan.",
        "• Setiap kutipan harus bersumber dari rilis/pernyataan resmi, bukan interpretasi analis.",
        "",
        "Langkah implementasi:",
        "1. Verifikasi tautan bukti dan cocokkan dengan Unit terkait.",
        f"2. Susun draf {channel or 'komunikasi resmi'} dengan kata baku Indonesia.",
        "3. Tinjau Unit Hukum bila isu menyentuh regulasi atau penilaian individu.",
        "4. Tayangkan setelah disetujui pimpinan; pantau sentimen 48 jam.",
        f"Topik kebijakan: {category}.",
    ])
    return "\n".join(lines).strip()

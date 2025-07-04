# groq_utils.py
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os
import re
import time
from typing import Optional

from groq import Groq

# ── API KEY ─────────────────────────────────────────────────────────────────
#   • Gunakan ENV "GROQ_API_KEY" jika ada; fallback ke string di sini.
API_KEY = os.getenv(
    "GROQ_API_KEY",
    "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"
)

# ── CLIENT ──────────────────────────────────────────────────────────────────
client = Groq(api_key=API_KEY)

# ── MODEL NAMES ─────────────────────────────────────────────────────────────
_SUM_MODEL = "gemma2-9b-it"
_CLS_MODEL = "llama3-70b-8192"

# ── UNIVERSAL RETRY WRAPPER ─────────────────────────────────────────────────
def _retry_groq(
    prompt: str,
    model: str,
    max_retry: int = 3,
    default_wait: float = 12.0,
) -> Optional[str]:
    """
    Kirim prompt ke Groq dengan retry & exponential-like back-off
    bila terkena rate-limit atau error jaringan.
    """
    wait = default_wait
    for attempt in range(1, max_retry + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()

        except Exception as e:
            msg = str(e)
            # — Rate-limit —──────────────────────────────────────────
            if "rate_limit_exceeded" in msg or "Rate limit reached" in msg:
                m = re.search(r"in ([0-9.]+)s", msg)
                wait_time = float(m.group(1)) if m else wait
                wait_time = max(wait, wait_time)
                print(f"[Groq] Rate-limit; tunggu {wait_time:.1f}s "
                      f"(attempt {attempt})")
                time.sleep(wait_time)
                # Next loop
            else:
                # — Error lain; coba lagi sebentar —──────────────────
                print(f"[Groq] Error ({attempt}/{max_retry}): {e}")
                time.sleep(1.0)

    return None  # habis retry masih gagal


# ── SUMMARIZER ──────────────────────────────────────────────────────────────
def summarize(text: str, min_chars: int = 30) -> str:
    """
    Ringkas `text` (≥ `min_chars`) menjadi 2-3 kalimat fokus ekonomi.
    """
    if not text or len(text.strip()) < min_chars:
        return "Teks terlalu pendek atau kosong"

    prompt = (
        "Anda adalah model ringkasan berita berbahasa Indonesia yang sangat "
        "terfokus pada aspek ekonomi. Setiap kali diberi teks, cukup kembalikan "
        "ringkasan dalam 2–3 kalimat, tanpa judul, tanpa label apapun, dan "
        "tanpa penjelasan meta. Ringkas teks berikut menggunakan Bahasa "
        "Indonesia yang jelas dan alami. Ringkasan digunakan untuk analisis "
        "fenomena ekonomi di Brebes, jadi jika beritanya terkait ekonomi "
        "yang berkemungkinan berdampak di Brebes maka tolong ringkas dengan baik.\n"
        f"Teks:\n{text.strip()}\n\nRingkasan:"
    )

    res = _retry_groq(prompt, model=_SUM_MODEL)
    return res if res else "Ringkasan gagal"


# ── CLASSIFIER ──────────────────────────────────────────────────────────────
_BASE_PROMPT = """\
Anda adalah model pemrosesan berita berbahasa Indonesia yang sangat terfokus \
pada aspek ekonomi di Brebes
Tentukan satu huruf (A–U) sesuai kategori utama dari teks berikut berdasarkan \
klasifikasi sektor ekonomi Indonesia, atau kosongkan jika tidak relevan atau \
tidak berdampak pada ekonomi Brebes:
   A: Pertanian, Kehutanan, Perikanan
   B: Pertambangan & Penggalian
   C: Industri Pengolahan
   D: Pengadaan Listrik & Gas
   E: Pengadaan Air, Pengelolaan Sampah/Limbah
   F: Konstruksi
   G: Perdagangan Besar/Eceran & Reparasi Kendaraan
   H: Transportasi & Pergudangan
   I: Akomodasi & Makan Minum
   J: Informasi & Komunikasi
   K: Keuangan & Asuransi
   L: Real Estate
   M: Jasa Perusahaan
   N: Jasa Profesional, Ilmiah & Teknis
   O: Administrasi Pemerintahan & Pertahanan
   P: Pendidikan
   Q: Kesehatan & Pekerjaan Sosial
   R: Seni, Hiburan & Rekreasi
   S: Jasa Lainnya
   T: Rumah Tangga sebagai Pemberi Kerja
   U: Organisasi Ekstrateritorial
   INGAT BAHWA HANYA BERITA YANG BERKAITAN DENGAN FENOMENA NERACA EKONOMI \
BREBES YANG DIBERIKAN KATEGORI
"""


def classify(text: str) -> str:
    """
    Kembalikan huruf kategori (A–U) atau 'R' (lain-lain/tidak relevan).
    """
    prompt = f"{_BASE_PROMPT}\n\nTeks:\n\"\"\"{text.strip()}\"\"\"\n\nKategori:"
    out = _retry_groq(prompt, model=_CLS_MODEL)

    if out and out[0].upper() in "ABCDEFGHIJKLMNOPQRSTU":
        return out[0].upper()
    return "R"  # default lain-lain


# ── MODULE TEST (opsional) ─────────────────────────────────────────────────
if __name__ == "__main__":
    sample = (
        "Harga cabai merah di Brebes turun tajam pekan ini "
        "karena panen raya dan lancarnya distribusi dari sentra produksi."
    )
    print("Ringkasan:", summarize(sample))
    print("Kategori :", classify(sample))

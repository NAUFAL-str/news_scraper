# classifier.py
import os, re, time
from groq import Groq

client = Groq(api_key="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")
MODEL = "llama3-70b-8192"

_BASE_PROMPT = """\
Anda adalah model pemrosesan berita berbahasa Indonesia yang sangat terfokus pada aspek ekonomi di Brebes
Tentukan satu huruf (A–U) sesuai kategori utama dari teks berikut berdasarkan klasifikasi sektor ekonomi Indonesia, atau kosongkan jika tidak relevan atau tidak berdampak pada ekonomi Brebes:
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
   INGAT BAHWA HANYA BERITA YANG BERKAITAN DENGAN FENOMENA NERACA EKONOMI BREBES YANG DIBERIKAN KATEGORI
"""

def _retry_groq(prompt: str, max_retry: int = 3):
    for attempt in range(1, max_retry + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            msg = str(e)
            if "rate_limit_exceeded" in msg:
                wait = float(re.search(r"in ([0-9.]+)s", msg).group(1))
                print(f"[Groq] Rate-limit klasifikasi; delay {wait}s")
                time.sleep(wait)
            else:
                print(f"[Groq] Err cls ({attempt}/{max_retry}): {e}")
                time.sleep(3)
    return None

def classify(text: str) -> str:
    prompt = f"{_BASE_PROMPT}\n\nTeks:\n\"\"\"{text.strip()}\"\"\"\n\nKategori:"
    out = _retry_groq(prompt)
    if out and out[0].upper() in "ABCDEFGHIJKLMNOPQRSTU":
        return out[0].upper()
    return "R"   # default lain-lain

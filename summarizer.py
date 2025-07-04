from __future__ import annotations
import os
from groq import Groq
from typing import Optional

client = Groq(api_key="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")
MODEL = "llama-3.3-70b-versatile"      # ganti jika perlu
# ──────────────────────────────────────────────────────────────────
def _retry_groq(prompt: str, max_retry: int = 3) -> Optional[str]:
    wait = 12        # detik default bila tidak ada petunjuk
    for attempt in range(1, max_retry + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content.strip()

        except Exception as e:
            msg = str(e)
            if "rate_limit_exceeded" in msg or "Rate limit reached" in msg:
                m = re.search(r"in ([0-9.]+)s", msg)
                wait_time = float(m.group(1)) if m else wait
                wait_time = max(wait, wait_time)
                print(f"[Groq] Rate-limit; tunggu {wait_time}s (attempt {attempt})")
                time.sleep(wait_time)
            else:
                print(f"[Groq] Error ({attempt}/{max_retry}): {e}")
                time.sleep(3)
    return None

# ──────────────────────────────────────────────────────────────────
def summarize(text: str, min_chars: int = 30) -> str:
    if not text or len(text.strip()) < min_chars:
        return "Teks terlalu pendek atau kosong"

    prompt = (
        "Anda adalah model ringkasan berita berbahasa Indonesia yang sangat terfokus pada aspek ekonomi. "
        "Setiap kali diberi teks, cukup kembalikan ringkasan dalam 2–3 kalimat, tanpa judul, tanpa label apapun, "
        "dan tanpa penjelasan meta. Ringkas teks berikut menggunakan Bahasa Indonesia yang jelas dan alami. "
        "Ringkasan digunakan untuk analisis fenomena ekonomi di Brebes, jadi jika beritanya terkait ekonomi "
        "yang berkemungkinan berdampak di Brebes maka tolong ringkas dengan baik.\n"
        f"Teks:\n{text.strip()}\n\nRingkasan:"
    )

    res = _retry_groq(prompt)
    return res if res else "Ringkasan gagal"

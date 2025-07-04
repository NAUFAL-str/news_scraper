"""
WEB2 (streaming)
────────────────────────────────────────────────────────────────────
• Scraping setiap situs tetap seri, tetapi setiap artikel yang ditemukan
  LANGSUNG dikirim ke antrean ringkasan/klasifikasi (ThreadPool).
• Ringkasan & klasifikasi Groq berjalan paralel while scraping continues.
• Progres tabel & bar di /progress/<task_id> ter-update real-time.
"""

from flask import (
    Flask, render_template, request,
    jsonify, redirect, url_for, send_file
)
import threading, queue, uuid, io, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from typing import Dict, List

# ── local modules ────────────────────────────────────────────────
from scraper_semua import (
    create_session,
    scrape_detik, scrape_kompas, scrape_beritasatu,
    scrape_panturapost, scrape_inews, scrape_antaranews,
    scrape_tvonenews, scrape_police, scrape_suarajelata,
    scrape_emsatunews, scrape_arahpantura, scrape_wp_rest,
    scrape_rss_search
)
from summarizer import summarize
from classifier  import classify

# daftar scraper agar mudah di-loop
SITE_SCRAPERS = [
    scrape_detik, scrape_kompas, scrape_beritasatu, scrape_panturapost,
    scrape_inews, scrape_antaranews, scrape_tvonenews, scrape_police,
    scrape_suarajelata, scrape_emsatunews, scrape_arahpantura,
    scrape_wp_rest, scrape_rss_search
]

# ── Flask & storage ──────────────────────────────────────────────
app  = Flask(__name__)
TASKS: Dict[str, Dict] = {}          # task_id ➜ state dict
LOCK  = threading.Lock()             # melindungi update TASKS

# ── util ─────────────────────────────────────────────────────────
def _safe(scraper, *args, **kw):
    """Jalankan scraper; bila error hanya log dan return list kosong."""
    try:
        return scraper(*args, **kw)
    except Exception as e:
        print(f"[WARN] {scraper.__name__} gagal: {e}")
        return []

# ── background workers ──────────────────────────────────────────
def process_article(task_id: str, art: dict):
    """
    Ringkas + klasifikasikan satu artikel, lalu update TASKS.
    Dipanggil di thread pool executor.
    """
    text = art.get("content", "").strip()
    if len(text) < 30:
        art["summary"]  = "Teks kosong"
        art["kategori"] = "R"
    else:
        art["summary"]  = summarize(text)
        art["kategori"] = classify(art["summary"])

    with LOCK:
        TASKS[task_id]["rows"].append(art)
        TASKS[task_id]["done"] += 1


def master_worker(task_id: str, keyword: str, max_articles: int):
    """
    1. Scrape tiap situs (seri) → setiap artikel disubmit ke ThreadPool.
    2. ThreadPool max_workers=4 memproses ringkas+klasifikasi paralel.
    3. Setelah semua scraping selesai, tunggu antrean selesai, set finished.
    """
    sess  = create_session()
    q_art = queue.Queue()            # antrean artikel sementara
    pool  = ThreadPoolExecutor(max_workers=2)

    # ─ inner thread: ambil dari queue ➜ submit ke pool
    def dispatcher():
        while True:
            art = q_art.get()
            if art is None:          # sentinel
                break
            with LOCK:
                TASKS[task_id]["total"] += 1
            pool.submit(process_article, task_id, art)
            q_art.task_done()

    disp_thr = threading.Thread(target=dispatcher, daemon=True)
    disp_thr.start()

    # ─ scraping loop (seri per situs, tapi cepat)
    for scraper in SITE_SCRAPERS:
        for art in _safe(scraper, keyword, max_articles, sess):
            q_art.put(art)

    # ─ selesai scraping
    q_art.join()         # tunggu antrean kosong
    q_art.put(None)      # hentikan dispatcher
    disp_thr.join()
    pool.shutdown(wait=True)

    with LOCK:
        TASKS[task_id]["finished"] = True
        TASKS[task_id]["ended_at"] = datetime.now().isoformat()


# ── ROUTES ───────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        kw   = request.form.get("keyword", "").strip()
        lim  = int(request.form.get("max_articles", "20") or 20)
        if not kw:
            return render_template("index.html", error="Keyword wajib diisi")

        tid = uuid.uuid4().hex[:8]
        TASKS[tid] = {
            "total": 0, "done": 0, "rows": [],
            "finished": False, "error": None,
            "started": datetime.now().isoformat()
        }
        threading.Thread(target=master_worker,
                         args=(tid, kw, lim),
                         daemon=True).start()
        return redirect(url_for("progress", task_id=tid))
    return render_template("index.html")


@app.route("/progress/<task_id>")
def progress(task_id: str):
    if task_id not in TASKS:
        return "Task not found", 404
    return render_template("progress.html", task_id=task_id)


@app.route("/status/<task_id>")
def status(task_id: str):
    data = TASKS.get(task_id)
    if not data:
        return jsonify({"error": "task not found"}), 404
    # kirim rows terakhir saja agar payload ringan
    slim_rows = data["rows"][-20:]
    return jsonify({**data, "rows": slim_rows})

# ── download endpoint ──────────────────────────────────────────────
@app.route("/download/<task_id>/<fmt>")
def download(task_id, fmt):
    data = TASKS.get(task_id)
    if not data or not data["finished"]:
        return "Belum selesai atau task tidak ada", 404

    df = pd.DataFrame(data["rows"])
    df = df[["site","tanggal","title","summary","kategori","link"]]

    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(
            io.BytesIO(buf.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"hasil_{task_id}.csv"
        )

    elif fmt in ("xlsx", "excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Data")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"hasil_{task_id}.xlsx"
        )
    else:
        return "Format tidak dikenali", 400

# ── RUN ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # No reloader agar thread tidak reset
    app.run(debug=True, use_reloader=False)

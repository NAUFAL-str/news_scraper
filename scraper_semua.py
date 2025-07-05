import csv
import time
import datetime
import re
import requests
import html
import feedparser
import warnings
from bs4 import BeautifulSoup
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Global headers for all requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    )
}

# Retry session factory
def create_session(retries: int = 3, backoff: float = 1):
    sess = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=[429,500,502,503,504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update(HEADERS)
    return sess

def _safe(callable_, *args, **kwargs):
    """Jalankan scraper situs; jika gagal, log & kembalikan list kosong."""
    try:
        return callable_(*args, **kwargs)
    except Exception as e:
        print(f"[WARN] {callable_.__name__} gagal: {e}")
        return []

# DETIK.COM scraper
MONTH_MAP_DETIK = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"Mei":5,"Jun":6,
                   "Jul":7,"Agt":8,"Sep":9,"Okt":10,"Nov":11,"Des":12}

def parse_detik_date(raw: str) -> str:
    try:
        part = raw.split(",",1)[1].strip()
        seg = part.split()
        return f"{int(seg[0]):02d}/{MONTH_MAP_DETIK.get(seg[1],0):02d}/{int(seg[2])}"
    except:
        return raw

def scrape_detik(keyword: str, max_articles: int, session: requests.Session):
    results = []
    count, page = 0, 1
    while count < max_articles:
        url = f"https://www.detik.com/search/searchnews?query={keyword}&sortby=time&page={page}"
        print(f"[Detik] GET {url}")
        resp = session.get(url, timeout=10); resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.find_all("article", class_="list-content__item")
        if not items: break
        for art in items:
            if count >= max_articles: break
            a = art.find("a", href=True)
            link = a['href']; title = art.find("h3", class_="media__title").get_text(strip=True)
            # detail
            try:
                d = session.get(link, timeout=10); d.raise_for_status()
                ds = BeautifulSoup(d.text, "lxml")
                paras = ds.find_all("div", class_="detail__body-text itp_bodycontent")
                content = " ".join(p.get_text(strip=True)
                                       for block in paras for p in block.find_all("p"))
            except:
                content = ""
            raw = art.find("span", attrs={"d-time": True})
            tanggal = parse_detik_date(raw['title']) if raw and raw.has_attr('title') else ""
            results.append({'site':'detik','tanggal':tanggal,'title':title,'content':content,'link':link})
            count += 1; print(f"   ✅ [Detik {count}] {title[:50]}…")
        page += 1
    return results

# KOMPAS.COM scraper
MONTH_MAP = {
    "Jan": 1, "Januari": 1,
    "Feb": 2, "Februari": 2,
    "Mar": 3, "Maret": 3,
    "Apr": 4, "April": 4,
    "May": 5, "Mei": 5,
    "Jun": 6, "Juni": 6,
    "Jul": 7, "Juli": 7,
    "Aug": 8, "Agu": 8, "Agt": 8, "Agustus": 8,
    "Sep": 9, "Sept": 9, "September": 9,
    "Oct": 10, "Okt": 10, "Oktober": 10,
    "Nov": 11, "November": 11,
    "Dec": 12, "Des": 12, "Desember": 12
}

def parse_kompas_date(raw: str) -> str:
    parts = raw.strip().split()
    if len(parts) >= 3:
        try:
            d = int(parts[0])
            m = MONTH_MAP.get(parts[1], 0)
            y = int(parts[2])
            if m:
                return f"{d:02d}/{m:02d}/{y}"
        except:
            pass
    return raw

def scrape_kompas(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape Kompas.com search untuk `keyword` hingga `max_articles`.
    Mengembalikan list dict: [{'site','tanggal','title','content','link'}, ...]
    """
    results = []
    scraped = 0
    page = 1
    while scraped < max_articles:
        url = f"https://search.kompas.com/search?q={keyword}&page={page}"
        print(f"[Kompas] GET {url}")
        try:
            resp = session.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Kompas] Gagal muat halaman {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        wrapper = soup.find("div", class_="articleList -list")
        items = wrapper.find_all("div", class_="articleItem") if wrapper else []
        if not items:
            print("[Kompas] Tidak ada artikel lagi.")
            break

        for art in items:
            if scraped >= max_articles:
                break

            a = art.find("a", class_="article-link", href=True)
            if not a:
                continue
            link = a["href"]
            title_tag = art.find("h2", class_="articleTitle")
            title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)

            date_tag = art.find("div", class_="articlePost-date")
            raw = date_tag.get_text(strip=True) if date_tag else ""
            tanggal = parse_kompas_date(raw)

            content = ""
            try:
                d = session.get(link, headers=HEADERS, timeout=10)
                d.raise_for_status()
                ds = BeautifulSoup(d.text, "lxml")
                cont = ds.find("div", class_="read__content")
                if cont:
                    paras = cont.find_all("p")
                    parts = []
                    for p in paras:
                        if p.find("strong") and p.find("a", class_="inner-link-baca-juga"):
                            continue
                        txt = p.get_text(" ", strip=True)
                        if txt:
                            parts.append(txt)
                    content = " ".join(parts)
            except Exception as e:
                print(f"[Kompas] Gagal ambil content dari {link}: {e}")

            results.append({'site':'kompas','tanggal':tanggal,'title':title,'content':content,'link':link})
            scraped += 1
            print(f"   ✅ [Kompas {scraped}] {title[:50]}…")
            time.sleep(0.5)

        page += 1
    return results

# BERITASATU.COM scraper
def scrape_beritasatu(keyword: str, max_articles: int, session: requests.Session):
    results=[]; scraped, page = 0,1
    while scraped<max_articles:
        url=f"https://www.beritasatu.com/search/{keyword}/{page}"
        print(f"[BeritaSatu] GET {url}")
        resp=session.get(url,timeout=10); resp.raise_for_status()
        soup=BeautifulSoup(resp.text,"html.parser")
        rows=soup.select("div.row.mt-4.position-relative")
        if not rows: break
        for row in rows:
            if scraped>=max_articles: break
            a=row.find("a",class_="stretched-link",href=True)
            link=a['href'];
            if link.startswith("/"): link="https://www.beritasatu.com"+link
            judul=row.find("h2",class_="h5 fw-bold").get_text(strip=True)
            raw=row.select_one("span.b1-date.text-muted small").get_text(strip=True).split("|")[0].strip()
            try: dt=datetime.datetime.strptime(raw,"%d %b %Y"); tanggal=dt.strftime("%d/%m/%Y")
            except: tanggal=raw
            art=session.get(link,timeout=10); art.raise_for_status(); asp=BeautifulSoup(art.text,"html.parser")
            paras=asp.select_one("div.col.b1-article.body-content") or asp.select_one("article.main")
            content=" ".join(p.get_text(strip=True) for p in paras.find_all("p"))
            results.append({'site':'beritasatu','tanggal':tanggal,'title':judul,'content':content,'link':link})
            scraped+=1; print(f"   ✅ [BeritaSatu {scraped}] {judul[:50]}…"); time.sleep(0.5)
        page+=1
    return results
    
# PANTURAPOST.COM scraper (revisi)
MONTH_MAP_PANTURA = {
    "Januari": "01", "Februari": "02", "Maret": "03", "April": "04",
    "Mei": "05",    "Juni":    "06", "Juli":  "07",   "Agustus":  "08",
    "September": "09","Oktober": "10","November":"11","Desember":"12"
}

def parse_pantura_date(raw: str) -> str:
    try:
        part = raw.split(",", 1)[1].strip()
        date_str = part.split("|", 1)[0].strip()   # e.g. "3 Juli 2025"
        day, month_name, year = date_str.split()
        month = MONTH_MAP_PANTURA.get(month_name, "00")
        return f"{int(day):02d}/{month}/{year}"
    except:
        return raw

def scrape_panturapost(keyword: str, max_articles: int, session: requests.Session):
    results = []
    count = 0
    page = 1

    while count < max_articles:
        url = f"https://www.panturapost.com/search?q={keyword}&sort=latest&page={page}"
        print(f"[PanturaPost] GET {url}")
        resp = session.get(url, timeout=10)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        wrap = soup.find("div", class_="latest__wrap")
        items = wrap.find_all("div", class_="latest__item") if wrap else []
        if not items:
            break

        for item in items:
            if count >= max_articles:
                break

            right = item.find("div", class_="latest__right")
            a_tag = right.find("a", class_="latest__link", href=True) if right else None
            if not a_tag:
                continue
            link = a_tag["href"]
            title = a_tag.get_text(strip=True)

            date_tag = right.find("date", class_="latest__date") if right else None
            raw_date = date_tag.get_text(strip=True) if date_tag else ""
            tanggal = parse_pantura_date(raw_date)

            # fetch only <article class="read__content clearfix">
            content = ""
            try:
                art_res = session.get(link, timeout=10)
                art_res.raise_for_status()
                art_soup = BeautifulSoup(art_res.text, "lxml")
                article = art_soup.find("article", class_="read__content clearfix")
                paras = article.find_all("p") if article else []
                clean = [p.get_text(strip=True)
                         for p in paras
                         if not p.find("strong", class_="read__others")]
                content = " ".join(clean)
            except:
                content = ""

            results.append({
                'site': 'panturapost',
                'tanggal': tanggal,
                'title': title,
                'content': content,
                'link': link
            })
            count += 1
            print(f"   ✅ [PanturaPost {count}] {title[:40]}…")

        page += 1
        time.sleep(0.5)

    return results


# INEWS.ID scraper
MONTH_MAP_INEWS={**MONTH_MAP_PANTURA}
def parse_inews_date(raw:str)->str:
    try:
        part=raw.split(",",1)[1].split("-",1)[0].strip(); d,mon,y=part.split();
        return f"{int(d):02d}/{MONTH_MAP_INEWS.get(mon,'00')}/{y}"
    except: return raw

def scrape_inews(keyword:str, max_articles:int, session: requests.Session):
    results=[]; scraped,page=0,1
    while scraped<max_articles:
        url=f"https://www.inews.id/find?q={keyword}&page={page}"
        print(f"[iNews] GET {url}")
        r=session.get(url,timeout=10); r.raise_for_status(); soup=BeautifulSoup(r.text,"lxml")
        cards=soup.find_all("article",class_="cardArticle")
        if not cards: break
        for card in cards:
            if scraped>=max_articles: break
            a=card.select_one(".cardBody a[href]"); link=a['href'] if a['href'].startswith("http") else "https://www.inews.id"+a['href']
            title=card.select_one("h3.cardTitle").get_text(strip=True)
            det=session.get(link,timeout=10); det.raise_for_status(); ds=BeautifulSoup(det.text,"lxml")
            raw=ds.select_one(".timeAndShare .createdAt").get_text(strip=True) if ds.select_one(".timeAndShare .createdAt") else ""
            tanggal=parse_inews_date(raw)
            body=ds.select_one("section.mainBody article.bodyArticleWrapper")
            content_parts=[]
            if body:
                for p in body.find_all("p", recursive=False):
                    txt=p.get_text(strip=True)
                    if txt and not txt.startswith("Editor:"): content_parts.append(txt)
            for a2 in ds.select("ul.paginationContent a[href]"):
                href=a2['href']; sub=session.get(href,timeout=10); sub_soup=BeautifulSoup(sub.text,"lxml")
                sub_body=sub_soup.select_one("section.mainBody article.bodyArticleWrapper")
                if sub_body:
                    content_parts.extend(p.get_text(strip=True) for p in sub_body.find_all("p", recursive=False)
                                          if not p.get_text(strip=True).startswith("Editor:"))
            content=" ".join(content_parts)
            results.append({'site':'inews','tanggal':tanggal,'title':title,'content':content,'link':link})
            scraped+=1; print(f"   ✅ [iNews {scraped}] {title[:50]}…"); time.sleep(0.5)
        page+=1
    return results

# ANTARANEWS scraper
MONTH_MAP_EN={"January":"01","February":"02","March":"03","April":"04",
             "May":"05","June":"06","July":"07","August":"08",
             "September":"09","October":"10","November":"11","December":"12"}

def parse_antara_date(raw:str)->str:
    try:
        part=raw.split("/",1)[1] if "/" in raw else raw
        tokens=part.strip().split()
        return f"{int(tokens[0]):02d}/{MONTH_MAP_EN.get(tokens[1],'00')}/{tokens[2]}"
    except: return raw

def scrape_antaranews(keyword:str, max_articles:int, session: requests.Session):
    results=[]; scraped,page=0,1
    while scraped<max_articles:
        url=(f"https://jateng.antaranews.com/search?q={keyword}&startDate=&endDate=&submit=Submit"
             if page==1 else f"https://jateng.antaranews.com/search/{keyword}/{page}")
        print(f"[Antara] GET {url}")
        r=session.get(url,timeout=10); r.raise_for_status(); soup=BeautifulSoup(r.text,"lxml")
        items=soup.select("article.simple-post.simple-big.clearfix")
        if not items: break
        for art in items:
            if scraped>=max_articles: break
            a=art.select_one("header h3 a[href]"); title=a.get_text(strip=True); link=a['href']
            if link.startswith("/"): link="https://jateng.antaranews.com"+link
            share=art.select_one("header p.simple-share"); raw=share.get_text(" ",strip=True) if share else ""
            tanggal=parse_antara_date(raw)
            try:
                det=session.get(link,timeout=10); ds=BeautifulSoup(det.text,"lxml")
                cont=ds.select_one("div.post-content.clearfix.font17[itemprop=articleBody]")
                paras=cont.find_all("p") if cont else []
                content=" ".join(p.get_text(" ",strip=True) for p in paras if p.get_text(strip=True))
            except:
                content=""
            results.append({'site':'antara','tanggal':tanggal,'title':title,'content':content,'link':link})
            scraped+=1; print(f"   ✅ [Antara {scraped}] {title[:60]}…")
        page+=1; time.sleep(0.5)
    return results

# TVONENEWS scraper
def scrape_tvonenews(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape TVOneNews.com untuk `keyword` hingga `max_articles`.
    Mengembalikan list dict: [{'site','tanggal','title','content','link'},...]
    """
    results=[]; scraped,page=0,1
    while scraped<max_articles:
        url=f"https://www.tvonenews.com/cari?q={keyword}&page={page}"
        print(f"[TVOne] GET {url}")
        resp=session.get(url,timeout=10); resp.raise_for_status()
        listing=BeautifulSoup(resp.text,"lxml")
        container=listing.find("div",id="load-content") or listing.find("div",class_="article-list-container")
        rows=container.find_all("div",class_="article-list-row") if container else []
        if not rows: break
        for row in rows:
            if scraped>=max_articles: break
            a=row.select_one("div.article-list-info a.ali-title")
            if not a: continue
            title=a.get_text(strip=True); link=a['href']
            if link.startswith("/"): link="https://www.tvonenews.com"+link
            date_tag=row.select_one("div.article-list-info ul.ali-misc li.ali-date span")
            raw=date_tag.get_text(strip=True) if date_tag else ""
            part=raw.split("-",1)[0].strip()
            try:
                d,m,y=part.split("/"); tanggal=f"{int(d):02d}/{int(m):02d}/{int(y)}"
            except:
                tanggal=part
            detail_url=link+("&page=all" if "?" in link else "?page=all")
            content=""
            try:
                dresp=session.get(detail_url,timeout=10); dresp.raise_for_status()
                dsoup=BeautifulSoup(dresp.text,"lxml")
                detail=dsoup.find("div",class_="detail-content")
                paras=detail.find_all("p") if detail else []
                parts=[p.get_text(" ",strip=True) for p in paras
                       if (txt:=p.get_text(strip=True)) and "advertisement" not in txt.lower()]
                content=" ".join(parts)
            except Exception as e:
                print(f"[TVOne] detail failed: {e}")
            results.append({'site':'tvone','tanggal':tanggal,'title':title,'content':content,'link':link})
            scraped+=1; print(f"   ✅ [Antara {scraped}] {title[:60]}…")
        page+=1; time.sleep(0.5)
    return results

# Scrape IndonesianPoliceNews (new)
MONTH_MAP_POLICE = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
    "Mei": 5,     "Juni":    6, "Juli": 7,    "Agustus": 8,
    "September": 9, "Oktober": 10, "November": 11, "Desember": 12
}

def parse_date_indo(raw: str) -> str:
    parts = raw.strip().split()
    if len(parts) >= 3:
        try:
            day = int(parts[0])
            mon = MONTH_MAP_POLICE.get(parts[1], 0)
            year = int(parts[2])
            if 1 <= mon <= 12:
                return f"{day:02d}/{mon:02d}/{year}"
        except:
            pass
    return raw


def scrape_police(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape IndonesianPoliceNews.id for `keyword` up to `max_articles`.
    Returns list of dicts with keys: site, tanggal, title, content, link.
    """
    results = []
    scraped = 0
    page = 1
    while scraped < max_articles:
        if page == 1:
            url = f"https://indonesianpolicenews.id/?s={keyword}"
        else:
            url = f"https://indonesianpolicenews.id/page/{page}/?s={keyword}"
        print(f"[Police] GET {url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        wrapper = soup.find("div", id="recent-content", class_="content-loop")
        cards = wrapper.select("div.post.type-post") if wrapper else []
        if not cards:
            print("[Police] No more articles.")
            break
        for card in cards:
            if scraped >= max_articles:
                break
            a = card.select_one("h2.entry-title a")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = a["href"]
            date_tag = card.select_one("span.entry-date")
            raw = date_tag.get_text(strip=True) if date_tag else ""
            tanggal = parse_date_indo(raw)
            content = ""
            try:
                det = session.get(link, timeout=10)
                det.raise_for_status()
                dsoup = BeautifulSoup(det.text, "lxml")
                cont = dsoup.find("div", class_="entry-content")
                paras = cont.find_all("p") if cont else []
                texts = []
                for p in paras:
                    txt = p.get_text(" ", strip=True)
                    if not txt or txt.lower().startswith("read more"):
                        continue
                    if "advertisement" in txt.lower():
                        continue
                    texts.append(txt)
                content = " ".join(texts)
            except Exception as e:
                print(f"[Police] detail failed: {e}")
            results.append({'site':'police','tanggal':tanggal,'title':title,'content':content,'link':link})
            scraped+=1; print(f"   ✅ [PoliceNews {scraped}] {title[:60]}…")
        page+=1; time.sleep(0.5)
    return results

# SuaraJelata scraper
def scrape_suarajelata(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape SuaraJelata.com for `keyword` up to `max_articles`.
    Returns list of dicts: {site, tanggal, title, content, link}
    """
    results = []
    scraped = 0
    paged = 1
    while scraped < max_articles:
        url = f"https://suarajelata.com/?s={keyword}&post_type%5B%5D=post&paged={paged}"
        print(f"[SuaraJelata] GET {url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        container = soup.find("div", id="infinite-container")
        if not container:
            print("[SuaraJelata] Container tidak ditemukan, berhenti.")
            break
        cards = container.find_all("article", class_="post type-post hentry")
        if not cards:
            print("[SuaraJelata] Tidak ada artikel lagi, berhenti.")
            break

        for card in cards:
            if scraped >= max_articles:
                break
            a = card.select_one("h2.entry-title a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = a["href"].strip()
            # parse tanggal
            time_tag = card.select_one("time.entry-date.published")
            if time_tag and time_tag.has_attr("datetime"):
                iso = time_tag["datetime"].split("T")[0]
                y, m, d = iso.split("-")
                tanggal = f"{d}/{m}/{y}"
            else:
                tanggal = time_tag.get_text(strip=True) if time_tag else ""
            # fetch detail
            content = ""
            try:
                det = session.get(link, timeout=10)
                det.raise_for_status()
                dsoup = BeautifulSoup(det.text, "lxml")
                cont = dsoup.find(
                    "div", class_="entry-content entry-content-single clearfix"
                )
                paras = cont.find_all("p") if cont else []
                texts = []
                for p in paras:
                    txt = p.get_text(" ", strip=True)
                    if not txt or txt.lower().startswith("scroll untuk lanjut"):
                        continue
                    texts.append(txt)
                content = " ".join(texts)
            except Exception as e:
                print(f"[SuaraJelata] Gagal ambil detail {link}: {e}")

            results.append({
                'site': 'suarajelata',
                'tanggal': tanggal,
                'title': title,
                'content': content,
                'link': link
            })
            scraped += 1; print(f"   ✅ [SuaraJelata {scraped}] {title[:40]}…")
        paged += 1; time.sleep(0.5)
    return results

# EmsatuNews scraper
MONTH_MAP_EMSATU = {
    "Januari": "01", "Februari": "02", "Maret": "03", "April": "04",
    "Mei": "05",    "Juni":     "06", "Juli":  "07",   "Agustus": "08",
    "September":"09","Oktober": "10","November":"11","Desember":"12"
}

def parse_date_emsatu(raw: str) -> str:
    parts = raw.split()
    for i in range(len(parts)-2):
        day, mon, year = parts[i], parts[i+1], parts[i+2]
        if day.isdigit() and mon in MONTH_MAP_EMSATU:
            return f"{int(day):02d}/{MONTH_MAP_EMSATU[mon]}/{year}"
    return raw.strip()

def scrape_emsatunews(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape EmsatuNews.co.id up to `max_articles` for `keyword`.
    Returns list of dicts: {site, tanggal, title, content, link}
    """
    results = []
    scraped = 0
    page = 1
    while scraped < max_articles:
        if page == 1:
            url = f"https://emsatunews.co.id/?s={keyword}&post_type%5B%5D=post"
        else:
            url = f"https://emsatunews.co.id/page/{page}/?s={keyword}&post_type%5B%5D=post"
        print(f"[EmsatuNews] GET {url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        container = soup.find("div", id="infinite-container")
        cards = container.find_all("article", class_="post type-post hentry") if container else []
        if not cards:
            print("[EmsatuNews] Tidak ada artikel lagi, berhenti.")
            break
        for card in cards:
            if scraped >= max_articles:
                break
            a = card.select_one("div.box-content h2.entry-title a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = a["href"].strip()
            # parse tanggal
            time_tag = card.select_one("time.entry-date.published")
            if time_tag and time_tag.has_attr("datetime"):
                iso = time_tag["datetime"].split("T")[0]
                y, m, d = iso.split("-")
                tanggal = f"{d}/{m}/{y}"
            else:
                raw = time_tag.get_text(" ", strip=True) if time_tag else ""
                tanggal = parse_date_emsatu(raw)
            # fetch detail
            content = ""
            try:
                det = session.get(link, timeout=10)
                det.raise_for_status()
                dsoup = BeautifulSoup(det.text, "lxml")

                # Coba container utama
                cont = dsoup.find(
                    "div", 
                    class_="entry-content entry-content-single clearfix have-stickybanner"
                )
                # fallback jika class berbeda
                if not cont:
                    cont = dsoup.find("div", class_="single-wrap")

                parts = []
                if cont:
                    for child in cont.find_all(["p","div"], recursive=False):
                        cls = child.get("class") or []
                        # skip iklan / banner
                        if "idt-textinsidepost" in cls or any("gmr-banner" in c for c in cls):
                            continue
                        txt = child.get_text(" ", strip=True)
                        if txt:
                            parts.append(txt)
                    content = "\n".join(parts)

            except Exception as e:
                print(f"[EmsatuNews] Gagal ambil detail {link}: {e}")

            results.append({
                'site': 'emsatunews',
                'tanggal': tanggal,
                'title': title,
                'content': content,
                'link': link
            })
            scraped += 1;print(f"   ✅ [EmsatuNews {scraped}] {title[:50]}…")
        page += 1;time.sleep(0.5)
    return results

# ArahPantura scraper
def scrape_arahpantura(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape ArahPantura.id for `keyword` up to `max_articles`.
    Returns list of dicts: {site, tanggal, title, content, link}
    Uses CSS selector for article IDs instead of regex.
    """
    results = []
    scraped = 0
    page = 1
    while scraped < max_articles:
        if page == 1:
            url = f"https://arahpantura.id/?s={keyword}+"
        else:
            url = f"https://arahpantura.id/page/{page}/?s={keyword}+"
        print(f"[ArahPantura] GET {url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # select articles with id starting 'post-'
        cards = soup.select('article[id^="post-"]')
        if not cards:
            print("[ArahPantura] No more articles, stopping.")
            break
        for card in cards:
            if scraped >= max_articles:
                break
            link_tag = card.select_one("h2.post-title.entry-title a[href]")
            if not link_tag:
                continue
            title = link_tag.get_text(strip=True)
            link = link_tag['href'].strip()
            # fetch detail page
            det = session.get(link, timeout=10)
            det.raise_for_status()
            dsoup = BeautifulSoup(det.text, "lxml")
            # parse tanggal
            tanggal = ""
            time_tag = dsoup.select_one("time.published[datetime]")
            if time_tag:
                iso = time_tag['datetime'].split('T')[0]
                try:
                    dt_obj = datetime.fromisoformat(iso)
                    tanggal = dt_obj.strftime("%d/%m/%Y")
                except:
                    tanggal = iso
            # extract content
            entry = dsoup.select_one("div.entry-inner")
            content = ""
            if entry:
                paras = entry.find_all("p")
                texts = [p.get_text(" ", strip=True)
                         for p in paras
                         if p.get_text(strip=True)
                         and not p.select_one("div.crp_related, div.wp-caption")]
                content = " ".join(texts)
            results.append({
                'site': 'arahpantura',
                'tanggal': tanggal,
                'title': title,
                'content': content,
                'link': link
            })
            scraped += 1;print(f"   ✅ [ArahPantura {scraped}] {title[:60]}…")
        page += 1;time.sleep(0.5)
    return results

# WP-REST API scraper
DOMAINS = [
    "suarabaru.id",
    "suarajelata.com",
    "portalpantura.com",
    "brebesinfo.com",
    "korantegal.com",
    "brebesnews.co",
    "beritakota.id",
    "tribuntipikor.com",
    "editorindonesia.com"
]

def parse_iso_date(iso: str) -> str:
    """
    Ubah ISO date 'YYYY-MM-DDTHH:MM:SS' → 'DD/MM/YYYY'
    """
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return iso.split("T")[0] if "T" in iso else iso


def scrape_wp_rest(keyword: str, max_posts_per_domain: int, session: requests.Session):
    """
    Query WP-REST API untuk setiap domain di DOMAINS
    Returns list of dicts: {site, tanggal, title, content, link}
    """
    results = []
    for domain in DOMAINS:
        api_url = f"https://{domain}/wp-json/wp/v2/posts?search={keyword}"
        try:
            resp = session.get(api_url, timeout=10)
            resp.raise_for_status()
            posts = resp.json()
        except Exception as e:
            print(f"[WP-REST] Gagal fetch {domain}: {e}")
            continue

        for post in posts[:max_posts_per_domain]:
            iso = post.get("date", "")
            tanggal = parse_iso_date(iso)
            judul = html.unescape(post.get("title", {}).get("rendered", ""))
            link = post.get("link", "")
            konten_html = post.get("content", {}).get("rendered", "")
            content = BeautifulSoup(konten_html, "html.parser").get_text(separator=" ", strip=True)
            results.append({
                'site': domain,
                'tanggal': tanggal,
                'title': judul,
                'content': content,
                'link': link
            })
        print(f"[WP-REST] Selesai domain: ✅ [{domain}] ({min(len(posts), max_posts_per_domain)} posts)")
    return results

# RSS Search scraper
def scrape_rss_search(keyword: str, max_articles: int, session: requests.Session):
    """
    Scrape RSS-search for PWMJateng.com and UMJ.ac.id up to max_articles each.
    Returns list of dicts: {site, tanggal, title, content, link},
    where `tanggal` is normalized to DD/MM/YYYY.
    """
    results = []
    rss_domains = ["pwmjateng.com", "umj.ac.id"]
    # suppress SSL warnings if verify=False
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    for domain in rss_domains:
        rss_url = f"https://{domain}/?s={keyword}&feed=rss2"
        print(f"[RSS] GET {rss_url}")
        try:
            resp = session.get(rss_url, timeout=10, verify=False)
            resp.raise_for_status()
        except Exception as e:
            print(f"[RSS] Gagal fetch {domain}: {e}")
            continue

        feed = feedparser.parse(resp.text)
        count = 0

        for entry in feed.entries:
            if count >= max_articles:
                break

            # 1) Parse published date into DD/MM/YYYY
            raw_pub = entry.get("published", "") or entry.get("updated", "")
            tanggal = raw_pub
            try:
                # Try RFC‐822 / RFC‐1123
                dt = datetime.strptime(raw_pub, "%a, %d %b %Y %H:%M:%S %z")
                tanggal = dt.strftime("%d/%m/%Y")
            except Exception:
                try:
                    # Fallback: ISO8601 style
                    dt = datetime.fromisoformat(raw_pub)
                    tanggal = dt.strftime("%d/%m/%Y")
                except Exception:
                    # leave as-is if unparseable
                    tanggal = raw_pub.split()[1] if raw_pub else ""

            # 2) Title & link
            judul = html.unescape(entry.get("title", ""))
            link  = entry.get("link", "")

            # 3) Summary → plain text
            konten_html = entry.get("summary", "") or entry.get("description", "")
            isi = BeautifulSoup(konten_html, "html.parser")\
                    .get_text(" ", strip=True)

            results.append({
                "site":    domain,
                "tanggal": tanggal,
                "title":   judul,
                "content": isi,
                "link":    link
            })
            count += 1

        print(f"[RSS] ✅ {domain}: {count} item(s)")

    return results

# ─────────────────── fungsi reusable utk Flask ───────────────────
def scrape_all(keyword: str,
               max_articles: int = 999,
               session: requests.Session | None = None) -> list[dict]:
    """Jalankan seluruh scraper dan kembalikan list dict artikel."""
    session = session or create_session()
    data: list[dict] = []

    data += _safe(scrape_detik, keyword,     max_articles, session)
    data += _safe(scrape_kompas,keyword,     max_articles, session)
    data += _safe(scrape_beritasatu,keyword, max_articles, session)
    data += _safe(scrape_panturapost,keyword,max_articles, session)
    data += _safe(scrape_inews,keyword,      max_articles, session)
    data += _safe(scrape_antaranews,keyword, max_articles, session)
    data += _safe(scrape_tvonenews,keyword,  max_articles, session)
    data += _safe(scrape_police,keyword,     max_articles, session)
    data += _safe(scrape_suarajelata,keyword,max_articles, session)
    data += _safe(scrape_emsatunews,keyword, max_articles, session)
    data += _safe(scrape_arahpantura,keyword,max_articles, session)
    data += _safe(scrape_wp_rest,keyword,    max_articles, session)
    data += _safe(scrape_rss_search,keyword, max_articles, session)

    return data

# Main
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Aggregate scraper for multiple Indonesian news sites"
    )
    parser.add_argument(
        '--keyword', required=True,
        help='Search keyword for all sites'
    )
    parser.add_argument(
        '--max-articles', type=int, default=999,
        help='Max number of articles to scrape per site'
    )
    parser.add_argument(
        '--output', default=None,
        help='Output CSV file name (default: scraped_{keyword}.csv)'
    )
    args = parser.parse_args()

    session = create_session()
    all_data = []

    # scrape each site with same limit
    all_data.extend(scrape_detik(args.keyword,    args.max_articles, session))
    all_data.extend(scrape_kompas(args.keyword,   args.max_articles, session))
    all_data.extend(scrape_beritasatu(args.keyword, args.max_articles, session))
    all_data.extend(scrape_panturapost(args.keyword,args.max_articles, session))
    all_data.extend(scrape_inews(args.keyword,     args.max_articles, session))
    all_data.extend(scrape_antaranews(args.keyword, args.max_articles, session))
    all_data.extend(scrape_tvonenews(args.keyword,  args.max_articles, session))
    all_data.extend(scrape_police(args.keyword,    args.max_articles, session))
    all_data.extend(scrape_suarajelata(args.keyword,args.max_articles, session))
    all_data.extend(scrape_emsatunews(args.keyword,args.max_articles, session))
    all_data.extend(scrape_arahpantura(args.keyword,args.max_articles, session))
    all_data.extend(scrape_wp_rest(args.keyword,args.max_articles, session))
    all_data.extend(scrape_rss_search(args.keyword,args.max_articles, session))

    output_file = args.output or f"scraped_{args.keyword}.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['site','tanggal','title','content','link'])
        for item in all_data:
            writer.writerow([
                item.get('site',''),
                item.get('tanggal',''),
                item.get('title',''),
                item.get('content',''),
                item.get('link','')
            ])
    print(f" ✓ Saved {len(all_data)} articles to {output_file}")

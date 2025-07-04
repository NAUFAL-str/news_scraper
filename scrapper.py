# scrapper.py
from scraper_semua import scrape_all, create_session

def scrape(keyword: str, max_articles: int = 20) -> list[dict]:
    """Wrapper supaya app Flask cukup panggil satu fungsi."""
    session = create_session()
    return scrape_all(keyword, max_articles=max_articles, session=session)

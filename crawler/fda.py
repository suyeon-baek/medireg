"""FDA 크롤러 — Federal Register API + accessdata로 가이던스 수집"""
import json
import hashlib
import logging
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Federal Register API — FDA 의료기기 관련 공시
FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1/documents.json"

# FDA 리콜 RSS (현재 작동하는 URL)
FDA_RECALL_RSS = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medical-device-safety-communications/rss.xml"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _fetch_federal_register(session: requests.Session) -> list[dict]:
    """Federal Register API로 FDA 의료기기 관련 최신 공시 수집"""
    items = []
    params = {
        "conditions[agencies]": "food-and-drug-administration",
        "conditions[term]": "medical device guidance",
        "per_page": 20,
        "order": "newest",
        "fields[]": ["title", "publication_date", "html_url", "abstract", "document_number", "type"],
    }
    try:
        resp = session.get(FEDERAL_REGISTER_API, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for doc in data.get("results", [])[:20]:
            title = doc.get("title", "").strip()
            if not title:
                continue
            items.append({
                "id": f"fda_fr_{_hash(title)}",
                "source": "fda_federal_register",
                "country": "US",
                "doctype": "guidance",
                "title": title,
                "summary": (doc.get("abstract") or "")[:300],
                "link": doc.get("html_url", ""),
                "date": doc.get("publication_date", ""),
                "crawled_at": datetime.now().isoformat(),
            })
        logger.info("FDA Federal Register: %d items", len(items))
    except Exception as e:
        logger.warning("FDA Federal Register failed: %s", e)
    return items


def _fetch_federal_register_rules(session: requests.Session) -> list[dict]:
    """Federal Register API로 FDA 의료기기 규정/최종 규칙 수집"""
    items = []
    params = {
        "conditions[agencies]": "food-and-drug-administration",
        "conditions[term]": "medical devices",
        "conditions[type][]": "Rule",
        "per_page": 10,
        "order": "newest",
        "fields[]": ["title", "publication_date", "html_url", "abstract", "type"],
    }
    try:
        resp = session.get(FEDERAL_REGISTER_API, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for doc in data.get("results", [])[:10]:
            title = doc.get("title", "").strip()
            if not title:
                continue
            items.append({
                "id": f"fda_rule_{_hash(title)}",
                "source": "fda_rules",
                "country": "US",
                "doctype": "law",
                "title": title,
                "summary": (doc.get("abstract") or "")[:300],
                "link": doc.get("html_url", ""),
                "date": doc.get("publication_date", ""),
                "crawled_at": datetime.now().isoformat(),
            })
        logger.info("FDA Rules: %d items", len(items))
    except Exception as e:
        logger.warning("FDA Rules failed: %s", e)
    return items


def _fetch_recall_rss(session: requests.Session) -> list[dict]:
    """FDA 의료기기 안전 통신 RSS (작동 시)"""
    from bs4 import BeautifulSoup
    from email.utils import parsedate_to_datetime
    items = []
    try:
        resp = session.get(FDA_RECALL_RSS, timeout=15)
        ct = resp.headers.get("Content-Type", "")
        if resp.status_code != 200 or ("xml" not in ct and not resp.text.strip().startswith("<?xml")):
            logger.warning("FDA recall RSS not available (status=%d)", resp.status_code)
            return items
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item")[:10]:
            title = (item.find("title") or {}).get_text(strip=True)
            link = (item.find("link") or {}).get_text(strip=True)
            pub_date = (item.find("pubDate") or {}).get_text(strip=True)
            if not title:
                continue
            date_str = ""
            try:
                date_str = parsedate_to_datetime(pub_date).date().isoformat()
            except Exception:
                date_str = pub_date[:10] if pub_date else ""
            items.append({
                "id": f"fda_recall_{_hash(title)}",
                "source": "fda_recalls_rss",
                "country": "US",
                "doctype": "recall",
                "title": title,
                "summary": "",
                "link": link,
                "date": date_str,
                "crawled_at": datetime.now().isoformat(),
            })
        logger.info("FDA Recall RSS: %d items", len(items))
    except Exception as e:
        logger.warning("FDA Recall RSS failed: %s", e)
    return items


def crawl() -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    results.extend(_fetch_federal_register(session))
    results.extend(_fetch_federal_register_rules(session))
    results.extend(_fetch_recall_rss(session))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

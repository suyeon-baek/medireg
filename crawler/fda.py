"""FDA 크롤러 — Guidance Documents, Federal Register 수집"""
import re
import json
import hashlib
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# FDA OpenData API — 의료기기 가이던스 최신 목록
FDA_GUIDANCE_API = (
    "https://api.fda.gov/device/event.json"  # placeholder; real endpoint below
)

FDA_GUIDANCE_URL = (
    "https://www.fda.gov/medical-devices/device-advice-comprehensive-regulatory-assistance"
    "/guidance-documents-medical-devices-and-radiation-emitting-products"
)

# FDA RSS — 의료기기 신규 가이던스 피드 (공식 지원)
FDA_RSS_URLS = [
    {
        "id": "fda_guidance_rss",
        "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medical-devices/rss.xml",
        "label": "FDA 의료기기 가이던스 RSS",
        "country": "US",
        "doctype": "guidance",
    },
    {
        "id": "fda_recalls_rss",
        "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medical-device-recalls/rss.xml",
        "label": "FDA 의료기기 리콜 RSS",
        "country": "US",
        "doctype": "recall",
    },
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_rss(xml: str, source_id: str, country: str, doctype: str) -> list[dict]:
    soup = BeautifulSoup(xml, "xml")
    items = []
    for item in soup.find_all("item")[:20]:
        title = (item.find("title") or {}).get_text(strip=True)
        link = (item.find("link") or {}).get_text(strip=True)
        pub_date = (item.find("pubDate") or {}).get_text(strip=True)
        description = (item.find("description") or {}).get_text(strip=True)[:300]

        if not title:
            continue

        # pubDate → ISO date
        date_str = ""
        try:
            from email.utils import parsedate_to_datetime
            date_str = parsedate_to_datetime(pub_date).date().isoformat()
        except Exception:
            date_str = pub_date[:10] if pub_date else ""

        items.append({
            "id": f"{source_id}_{_hash(title)}",
            "source": source_id,
            "country": country,
            "doctype": doctype,
            "title": title,
            "summary": description,
            "link": link,
            "date": date_str,
            "crawled_at": datetime.utcnow().isoformat(),
        })
    return items


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for target in FDA_RSS_URLS:
        try:
            resp = session.get(target["url"], timeout=20)
            resp.raise_for_status()
            items = _parse_rss(resp.text, target["id"], target["country"], target["doctype"])
            results.extend(items)
            logger.info("FDA %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("FDA %s failed: %s", target["id"], e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

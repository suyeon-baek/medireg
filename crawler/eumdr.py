"""EU MDR/IVDR 크롤러 — EUR-Lex, EC Health 페이지 수집"""
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
    "Accept-Language": "en-US,en;q=0.9",
}

# EC Health — 의료기기 페이지 (guidance documents 목록)
EU_TARGETS = [
    {
        "id": "ec_mdr_guidance",
        "url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations/guidance-mdcg-endorsed-documents-and-other-guidance_en",
        "label": "MDCG Guidance Documents",
        "country": "EU",
        "doctype": "guidance",
        "selector": "a[href*='mdcg']",
    },
    {
        "id": "ec_mdr_news",
        "url": "https://health.ec.europa.eu/medical-devices-sector/new-regulations_en",
        "label": "EU MDR News",
        "country": "EU",
        "doctype": "notice",
        "selector": ".field--name-title a, h3 a, h2 a",
    },
]

# EUR-Lex RSS — EU 관보 의료기기 관련
EURLEX_RSS = {
    "id": "eurlex_meddev",
    "url": "https://eur-lex.europa.eu/search.html?SUBDOM_INIT=ALL_ALL&DTS_DOM=ALL&type=advanced&lang=en&andText0=medical+devices&qid=1&RSS=true",
    "label": "EUR-Lex 의료기기 관련 입법",
    "country": "EU",
    "doctype": "law",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_page(html: str, source_id: str, country: str, doctype: str, selector: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for el in soup.select(selector)[:25]:
        title = el.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        href = el.get("href", "")
        if href and not href.startswith("http"):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)

        key = _hash(title)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "id": f"{source_id}_{key}",
            "source": source_id,
            "country": country,
            "doctype": doctype,
            "title": title,
            "link": href,
            "date": "",
            "crawled_at": datetime.utcnow().isoformat(),
        })

    return items


def _parse_rss(xml: str, source_id: str, country: str, doctype: str) -> list[dict]:
    from bs4 import BeautifulSoup as BS
    soup = BS(xml, "xml")
    items = []
    for item in soup.find_all("item")[:15]:
        title = (item.find("title") or {}).get_text(strip=True)
        link = (item.find("link") or {}).get_text(strip=True)
        pub_date = (item.find("pubDate") or {}).get_text(strip=True)
        if not title:
            continue
        date_str = pub_date[:10] if pub_date else ""
        items.append({
            "id": f"{source_id}_{_hash(title)}",
            "source": source_id,
            "country": country,
            "doctype": doctype,
            "title": title,
            "link": link,
            "date": date_str,
            "crawled_at": datetime.utcnow().isoformat(),
        })
    return items


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for target in EU_TARGETS:
        try:
            resp = session.get(target["url"], timeout=25)
            resp.raise_for_status()
            items = _parse_page(
                resp.text,
                target["id"],
                target["country"],
                target["doctype"],
                target["selector"],
                target["url"],
            )
            results.extend(items)
            logger.info("EU %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("EU %s failed: %s", target["id"], e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

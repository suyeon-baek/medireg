"""PMDA (일본 의약품의료기기종합기구) 크롤러"""
import re
import json
import hashlib
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://www.pmda.go.jp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
}

TARGETS = [
    {
        "id": "pmda_notice",
        "url": f"{BASE}/medical_devices/0001.html",
        "label": "PMDA 의료기기 통지/가이던스",
        "country": "JP",
        "doctype": "guidance",
        "selector": "table.table01 a, .contents a",
    },
    {
        "id": "pmda_english",
        "url": f"{BASE}/english/devices/0001.html",
        "label": "PMDA Medical Devices (English)",
        "country": "JP",
        "doctype": "notice",
        "selector": "table a, .contents a",
    },
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_page(html: str, source_id: str, country: str, doctype: str, selector: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for el in soup.select(selector)[:20]:
        title = el.get_text(strip=True)
        if not title or len(title) < 5:
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


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for target in TARGETS:
        try:
            resp = session.get(target["url"], timeout=20)
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
            logger.info("PMDA %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("PMDA %s failed: %s", target["id"], e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

"""FDA 크롤러 — openFDA API + 공식 RSS 피드로 가이던스 수집"""
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
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# FDA 공식 RSS (봇 차단 우회를 위해 feedparser 호환 헤더 사용)
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

# 대체: FDA 가이던스 검색 페이지 (RSS 차단 시 fallback)
FDA_GUIDANCE_HTML = {
    "id": "fda_guidance_html",
    "url": "https://www.fda.gov/medical-devices/guidance-documents-medical-devices-and-radiation-emitting-products",
    "label": "FDA 의료기기 가이던스 목록",
    "country": "US",
    "doctype": "guidance",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_rss(xml_text: str, source_id: str, country: str, doctype: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for item in soup.find_all("item")[:20]:
        title = (item.find("title") or {}).get_text(strip=True)
        link = (item.find("link") or {}).get_text(strip=True)
        pub_date = (item.find("pubDate") or {}).get_text(strip=True)
        description = (item.find("description") or {}).get_text(strip=True)[:300]

        if not title:
            continue

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


def _parse_guidance_html(html: str, source_id: str) -> list[dict]:
    """RSS 차단 시 HTML 페이지에서 직접 파싱하는 fallback"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    # FDA 가이던스 목록: .lcds-list 또는 table 내 링크
    for a in soup.select("table a, .lcds-list a, ul.usa-list a")[:25]:
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.fda.gov" + href

        key = _hash(title)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "id": f"{source_id}_{key}",
            "source": source_id,
            "country": "US",
            "doctype": "guidance",
            "title": title,
            "summary": "",
            "link": href,
            "date": "",
            "crawled_at": datetime.utcnow().isoformat(),
        })
    return items


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for target in FDA_RSS_URLS:
        try:
            resp = session.get(target["url"], timeout=25)
            resp.raise_for_status()
            # XML 응답인지 확인
            ct = resp.headers.get("Content-Type", "")
            if "xml" in ct or resp.text.strip().startswith("<?xml"):
                items = _parse_rss(resp.text, target["id"], target["country"], target["doctype"])
                results.extend(items)
                logger.info("FDA RSS %s: %d items", target["id"], len(items))
            else:
                logger.warning("FDA RSS %s: unexpected content type %s", target["id"], ct)
        except Exception as e:
            logger.warning("FDA RSS %s failed: %s", target["id"], e)

    # RSS 모두 실패 시 HTML fallback
    if not results:
        try:
            t = FDA_GUIDANCE_HTML
            resp = session.get(t["url"], timeout=25)
            resp.raise_for_status()
            items = _parse_guidance_html(resp.text, t["id"])
            results.extend(items)
            logger.info("FDA HTML fallback: %d items", len(items))
        except Exception as e:
            logger.warning("FDA HTML fallback failed: %s", e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

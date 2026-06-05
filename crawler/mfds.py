"""식약처 (MFDS) 크롤러 — 고시, 가이던스, 공지사항 수집"""
import json
import hashlib
import logging
import time
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://www.mfds.go.kr"
TARGETS = [
    {
        "id": "mfds_notice",
        "label": "식약처 의료기기 공지사항",
        "url": f"{BASE}/brd/m_218/list.do",
        "country": "KR",
        "doctype": "notice",
    },
    {
        "id": "mfds_law",
        "label": "식약처 의료기기 법령/고시",
        "url": f"{BASE}/brd/m_211/list.do",
        "country": "KR",
        "doctype": "law",
    },
    {
        "id": "mfds_admin",
        "label": "식약처 의료기기 행정처분/허가",
        "url": f"{BASE}/brd/m_215/list.do",
        "country": "KR",
        "doctype": "guidance",
    },
    {
        "id": "mfds_approval",
        "label": "식약처 의료기기 허가 심사",
        "url": f"{BASE}/brd/m_220/list.do",
        "country": "KR",
        "doctype": "guidance",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.mfds.go.kr",
    "Connection": "keep-alive",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_list_page(html: str, page_url: str, source_id: str, country: str, doctype: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # 에러 페이지 감지
    if soup.select_one("div.error_page"):
        logger.warning("%s: error page returned", source_id)
        return items

    container = soup.select_one("div.bbs_list01")
    if not container:
        logger.warning("%s: div.bbs_list01 not found", source_id)
        return items

    rows = container.select("ul > li")
    for row in rows[:20]:
        if "notice_more" in row.get("class", []):
            continue

        title_el = row.select_one("a.title")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title:
            continue

        href = title_el.get("href", "")
        # urljoin으로 상대 URL 올바르게 처리 (./view.do?... 등)
        if href and not href.startswith("http"):
            href = urljoin(page_url, href)

        date_el = row.select_one("div.right_column")
        date_str = date_el.get_text(strip=True)[:10] if date_el else ""

        items.append({
            "id": f"{source_id}_{_hash(title)}",
            "source": source_id,
            "country": country,
            "doctype": doctype,
            "title": title,
            "link": href,
            "date": date_str,
            "crawled_at": datetime.now().isoformat(),
        })

    return items


def _fetch_with_retry(session: requests.Session, url: str, retries: int = 3, delay: float = 2.0):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp
        except requests.exceptions.ConnectionError as e:
            if attempt < retries - 1:
                logger.warning("Connection error on %s (attempt %d/%d), retrying...", url, attempt + 1, retries)
                time.sleep(delay * (attempt + 1))
            else:
                raise e
    return None


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for target in TARGETS:
        try:
            resp = _fetch_with_retry(session, target["url"])
            items = _parse_list_page(
                resp.text,
                target["url"],
                target["id"],
                target["country"],
                target["doctype"],
            )
            results.extend(items)
            logger.info("MFDS %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("MFDS %s failed: %s", target["id"], e)
        time.sleep(1.0)  # 서버 부하 방지

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

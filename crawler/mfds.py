"""식약처 (MFDS) 크롤러 — 고시, 가이던스, 공지사항 수집"""
import re
import json
import hashlib
import logging
from datetime import datetime
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
        "id": "mfds_guidance",
        "label": "식약처 의료기기 가이던스",
        "url": f"{BASE}/brd/m_217/list.do",
        "country": "KR",
        "doctype": "guidance",
    },
    {
        "id": "mfds_law",
        "label": "식약처 의료기기 법령/고시",
        "url": f"{BASE}/brd/m_211/list.do",
        "country": "KR",
        "doctype": "law",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.mfds.go.kr",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_list_page(html: str, source_id: str, country: str, doctype: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # 실제 구조: div.bbs_list01 > ul > li
    container = soup.select_one("div.bbs_list01")
    if not container:
        logger.warning("%s: div.bbs_list01 not found", source_id)
        return items

    rows = container.select("ul > li")
    for row in rows[:20]:
        # 공지 확장 버튼(notice_more) 제외
        if "notice_more" in row.get("class", []):
            continue

        title_el = row.select_one("a.title")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title:
            continue

        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = BASE + href

        date_el = row.select_one("div.right_column")
        date_str = date_el.get_text(strip=True) if date_el else ""
        # "2026-05-29" 형식 그대로 사용
        date_str = date_str[:10] if date_str else ""

        items.append({
            "id": f"{source_id}_{_hash(title)}",
            "source": source_id,
            "country": country,
            "doctype": doctype,
            "title": title,
            "link": href,
            "date": date_str,
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
            resp.encoding = "utf-8"
            items = _parse_list_page(
                resp.text,
                target["id"],
                target["country"],
                target["doctype"],
            )
            results.extend(items)
            logger.info("MFDS %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("MFDS %s failed: %s", target["id"], e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

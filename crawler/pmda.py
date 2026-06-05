"""PMDA (일본 의약품의료기기종합기구) 크롤러"""
import json
import hashlib
import logging
from datetime import datetime
from urllib.parse import urljoin
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
    "Accept-Language": "en-US,en;q=0.9",
}

# 실제 유효 URL (0001.html은 404)
TARGETS = [
    {
        "id": "pmda_regulatory",
        "url": f"{BASE}/english/review-services/regulatory-info/0021.html",
        "label": "PMDA Medical Devices Regulatory Info",
        "country": "JP",
        "doctype": "guidance",
    },
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_pmda(html: str, source_id: str, base_url: str) -> list[dict]:
    """PMDA 영문 의료기기 규제정보 페이지 파싱
    구조: div.inner.editor > ul > li > a (제목) + 인접 p.ml20 (날짜)
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    container = soup.select_one("div.inner.editor")
    if not container:
        # fallback: 전체 페이지에서 링크 수집
        container = soup

    for li in container.select("ul li")[:30]:
        a = li.select_one("a")
        if not a:
            continue

        title = a.get_text(strip=True)
        # 파일 크기 표시 제거 "[1.2MB]"
        import re
        title = re.sub(r"\s*\[\d+[\d.]*\s*(KB|MB|GB)?\]\s*", "", title, flags=re.I).strip()

        if not title or len(title) < 5:
            continue

        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = urljoin(BASE, href)

        # 날짜: li 다음 형제 p.ml20
        date_str = ""
        next_el = li.find_next_sibling()
        if next_el and next_el.name == "p":
            date_str = next_el.get_text(strip=True)[:50]

        key = _hash(title)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "id": f"{source_id}_{key}",
            "source": source_id,
            "country": "JP",
            "doctype": "guidance",
            "title": title,
            "summary": date_str,
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
            items = _parse_pmda(resp.text, target["id"], target["url"])
            results.extend(items)
            logger.info("PMDA %s: %d items", target["id"], len(items))
        except Exception as e:
            logger.warning("PMDA %s failed: %s", target["id"], e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

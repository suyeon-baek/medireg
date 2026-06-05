"""EU MDR/IVDR 크롤러 — MDCG Guidance Documents 수집"""
import json
import hashlib
import logging
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://health.ec.europa.eu"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# 실제 HTML 구조: table.ecl-table > tbody > tr (제목/날짜/레퍼런스 3열)
MDCG_URL = (
    f"{BASE}/medical-devices-sector/new-regulations"
    "/guidance-mdcg-endorsed-documents-and-other-guidance_en"
)

EU_NEWS_URL = f"{BASE}/medical-devices-sector/new-regulations_en"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _parse_mdcg_tables(html: str) -> list[dict]:
    """MDCG 가이던스 테이블 파싱
    구조: table.ecl-table > tbody.ecl-table__body > tr > td × 3 (Reference, Title, Publication)
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for table in soup.select("table.ecl-table"):
        rows = table.select("tbody.ecl-table__body tr.ecl-table__row")
        for row in rows:
            cells = row.select("td.ecl-table__cell")
            if len(cells) < 2:
                continue

            # Reference 열 (첫 번째 td) — 문서번호 + 링크
            ref_cell = cells[0]
            ref_link = ref_cell.select_one("a")
            ref_text = ref_cell.get_text(strip=True)  # 예: "MDCG 2024-1"

            # Title 열 (두 번째 td)
            title_cell = cells[1]
            title_link = title_cell.select_one("a")
            title_text = title_cell.get_text(strip=True)

            # Publication 열 (세 번째 td, 있을 경우)
            date_text = cells[2].get_text(strip=True) if len(cells) >= 3 else ""

            if not title_text or len(title_text) < 5:
                continue

            # 제목이 언어코드(2자) + 언어명 조합이면 언어 선택 버튼 → 필터링
            if len(title_text) <= 20 and title_text[:2].islower() and not any(c.isdigit() for c in title_text):
                continue

            # 링크: ref_link 우선, 없으면 title_link
            href = ""
            for link_el in [ref_link, title_link]:
                if link_el:
                    href = link_el.get("href", "")
                    if href:
                        href = urljoin(BASE, href)
                        break

            # 전체 제목: "MDCG 2024-1 — 제목" 형태로 조합
            full_title = f"{ref_text} — {title_text}" if ref_text and ref_text not in title_text else title_text

            key = _hash(full_title)
            if key in seen:
                continue
            seen.add(key)

            items.append({
                "id": f"ec_mdr_guidance_{key}",
                "source": "ec_mdr_guidance",
                "country": "EU",
                "doctype": "guidance",
                "title": full_title,
                "link": href,
                "date": date_text,
                "crawled_at": datetime.utcnow().isoformat(),
            })

    return items


def crawl() -> list[dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. MDCG 가이던스 테이블
    try:
        resp = session.get(MDCG_URL, timeout=30)
        resp.raise_for_status()
        items = _parse_mdcg_tables(resp.text)
        results.extend(items)
        logger.info("EU MDCG 가이던스: %d items", len(items))
    except Exception as e:
        logger.warning("EU MDCG 가이던스 failed: %s", e)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = crawl()
    print(json.dumps(data, ensure_ascii=False, indent=2))

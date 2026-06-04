"""
메인 크롤러 실행 스크립트
- 각 규제기관 크롤링
- 이전 스냅샷과 비교해 변경 항목 감지
- data/updates.json 및 data/crawled.json 업데이트
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# crawler 패키지 경로 설정
sys.path.insert(0, str(Path(__file__).parent))

import mfds
import fda
import eumdr
import pmda

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_all")

DATA_DIR = Path(__file__).parent.parent / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CRAWLED_FILE = DATA_DIR / "crawled.json"
UPDATES_FILE = DATA_DIR / "updates.json"
META_FILE = DATA_DIR / "meta.json"


def load_json(path: Path) -> dict | list:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path: Path, data, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def detect_new_items(current: list[dict], previous: list[dict]) -> list[dict]:
    """이전 스냅샷에 없는 신규 항목 반환"""
    prev_ids = {item["id"] for item in previous}
    return [item for item in current if item["id"] not in prev_ids]


def run():
    now = datetime.now(timezone.utc)
    run_date = now.date().isoformat()

    logger.info("=== MediReg 크롤링 시작: %s ===", now.isoformat())

    # 1. 각 크롤러 실행
    crawlers = [
        ("MFDS", mfds.crawl),
        ("FDA", fda.crawl),
        ("EU MDR", eumdr.crawl),
        ("PMDA", pmda.crawl),
    ]

    all_items: list[dict] = []
    stats = {}

    for name, crawl_fn in crawlers:
        try:
            items = crawl_fn()
            all_items.extend(items)
            stats[name] = {"count": len(items), "status": "ok"}
            logger.info("%s: %d items 수집", name, len(items))
        except Exception as e:
            logger.error("%s 크롤링 실패: %s", name, e)
            stats[name] = {"count": 0, "status": "error", "error": str(e)}

    # 2. 이전 데이터 로드
    previous = load_json(CRAWLED_FILE)

    # 3. 신규 항목 감지
    new_items = detect_new_items(all_items, previous if isinstance(previous, list) else [])
    logger.info("신규 항목: %d건", len(new_items))

    # 4. updates.json 업데이트
    updates = load_json(UPDATES_FILE)
    if not isinstance(updates, list):
        updates = []

    for item in new_items:
        updates.insert(0, {
            "id": item["id"],
            "country": item.get("country", ""),
            "doctype": item.get("doctype", ""),
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "link": item.get("link", ""),
            "date": item.get("date", ""),
            "detected_at": now.isoformat(),
            "unread": True,
        })

    # 최대 200건 유지
    updates = updates[:200]

    # 5. 스냅샷 저장 (날짜별)
    snapshot_path = SNAPSHOT_DIR / f"{run_date}.json"
    save_json(snapshot_path, all_items)

    # 6. 현재 데이터 저장
    save_json(CRAWLED_FILE, all_items)
    save_json(UPDATES_FILE, updates)

    # 7. 메타 정보 저장
    meta = {
        "last_crawled": now.isoformat(),
        "total_items": len(all_items),
        "new_items": len(new_items),
        "stats": stats,
    }
    save_json(META_FILE, meta)

    logger.info("=== 완료: 전체 %d건, 신규 %d건 ===", len(all_items), len(new_items))
    return meta


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))

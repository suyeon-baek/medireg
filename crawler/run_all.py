"""
MediReg crawler - Active device + Software medical device only
Filters: software, SaMD, AI/ML, IEC 60601, cybersecurity, EMC, usability, etc.
MFDS removed (KR regulations not used).
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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

ACTIVE_SW_KEYWORDS = [
    "software", "samd", "artificial intelligence", "machine learning",
    "algorithm", "firmware", "digital health", "digital therapeutic", "dtx",
    "cybersecurity", "cyber security", "cyber-security",
    "iec 60601", "electrical", "active device", "active medical",
    "electromagnetic", "emc", "usability", "human factors",
    "iec 62304", "iec 62366", "iec 81001", "iso 14971",
    "pccp", "predetermined change", "real world evidence", "rwe",
    "mobile health", "mhealth", "wearable",
    "clinical decision support", "cds",
    "neural network", "deep learning", "ai/ml",
    "510(k)", "premarket notification", "premarket approval",
    "de novo", "qmsr", "quality management",
    "mdcg", "mdr annex",
    "total product lifecycle", "tplc",
]


def is_active_sw_relevant(item: dict) -> bool:
    text = " ".join([
        item.get("title", ""),
        item.get("summary", ""),
        item.get("body", ""),
    ]).lower()
    return any(kw in text for kw in ACTIVE_SW_KEYWORDS)


def load_json(path: Path):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path: Path, data, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def detect_new_items(current, previous):
    prev_ids = {item["id"] for item in previous}
    return [item for item in current if item["id"] not in prev_ids]


def run():
    now = datetime.now(timezone.utc)
    run_date = now.date().isoformat()
    logger.info("=== MediReg crawl start: %s ===", now.isoformat())

    crawlers = [
        ("FDA", fda.crawl),
        ("EU MDR", eumdr.crawl),
        ("PMDA", pmda.crawl),
    ]

    all_items = []
    stats = {}

    for name, crawl_fn in crawlers:
        try:
            items = crawl_fn()
            all_items.extend(items)
            stats[name] = {"count": len(items), "status": "ok"}
            logger.info("%s: %d items", name, len(items))
        except Exception as e:
            logger.error("%s failed: %s", name, e)
            stats[name] = {"count": 0, "status": "error", "error": str(e)}

    before = len(all_items)
    all_items = [item for item in all_items if is_active_sw_relevant(item)]
    logger.info("Keyword filter: %d -> %d (excluded %d)", before, len(all_items), before - len(all_items))

    previous = load_json(CRAWLED_FILE)
    new_items = detect_new_items(all_items, previous if isinstance(previous, list) else [])
    logger.info("New items: %d", len(new_items))

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

    updates = updates[:200]

    save_json(SNAPSHOT_DIR / f"{run_date}.json", all_items)
    save_json(CRAWLED_FILE, all_items)
    save_json(UPDATES_FILE, updates)
    save_json(META_FILE, {
        "last_crawled": now.isoformat(),
        "total_items": len(all_items),
        "new_items": len(new_items),
        "stats": stats,
    })

    logger.info("=== Done: %d total, %d new ===", len(all_items), len(new_items))
    return {"total_items": len(all_items), "new_items": len(new_items), "stats": stats}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))

"""
pipeline.py

Entry point that ties the scraper and database together into one run:
fetch -> parse -> store -> log summary. Designed to be invoked directly,
on a schedule (cron / Task Scheduler), or from a GitHub Actions workflow
(see .github/workflows/scrape.yml).
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

import yaml
import requests

sys.path.append(str(Path(__file__).resolve().parent))

from scraper import fetch_page, parse_page
from database import init_db, insert_snapshot, count_snapshots
from logger import get_logger


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline(config_path: str = "config/settings.yaml") -> int:
    config = load_config(config_path)

    logger = get_logger(
        "hn_tracker",
        config["logging"]["path"],
        level=config["logging"]["level"],
        max_bytes=config["logging"]["max_bytes"],
        backup_count=config["logging"]["backup_count"],
    )

    logger.info("=== Pipeline run started ===")

    scraper_cfg = config["scraper"]
    base_url = scraper_cfg["base_url"]
    pages = scraper_cfg.get("pages", 1)
    delay = scraper_cfg.get("request_delay_seconds", 2)

    conn = init_db(config["database"]["path"])
    total_inserted = 0

    with requests.Session() as session:
        for page_num in range(1, pages + 1):
            page_url = base_url if page_num == 1 else f"{base_url}/news?p={page_num}"
            logger.info(f"Fetching page {page_num}: {page_url}")

            html = fetch_page(
                page_url,
                session,
                user_agent=scraper_cfg["user_agent"],
                max_retries=scraper_cfg.get("max_retries", 3),
                backoff_base_seconds=scraper_cfg.get("backoff_base_seconds", 2),
            )

            if html is None:
                logger.error(f"Skipping page {page_num}: fetch failed after retries.")
                continue

            stories = parse_page(html)
            if not stories:
                logger.warning(f"No stories parsed from page {page_num}. "
                                f"Site structure may have changed.")
                continue

            inserted = insert_snapshot(conn, stories)
            total_inserted += inserted
            logger.info(f"Inserted {inserted} story snapshots from page {page_num}.")

            if page_num < pages:
                time.sleep(delay)

    total_rows = count_snapshots(conn)
    logger.info(f"Run complete. Inserted {total_inserted} rows this run "
                f"({total_rows} total rows in database).")
    logger.info("=== Pipeline run finished ===")

    conn.close()
    return total_inserted


if __name__ == "__main__":
    run_pipeline()

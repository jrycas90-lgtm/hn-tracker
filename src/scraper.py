"""
scraper.py

Handles fetching Hacker News front-page HTML (with retry/backoff for
transient failures) and parsing it into structured story records.

Parsing is isolated from network access on purpose: `parse_page` takes raw
HTML and returns data, with no requests inside it. That makes it trivially
unit-testable against a saved HTML fixture, and reusable if the fetch layer
ever changes (e.g. swapping requests for httpx, or reading from a cache).
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("hn_tracker")


@dataclass
class Story:
    story_id: str
    rank: int
    title: str
    url: Optional[str]
    domain: Optional[str]
    points: Optional[int]
    comments: Optional[int]


def fetch_page(url: str, session: requests.Session, user_agent: str,
                max_retries: int = 3, backoff_base_seconds: int = 2) -> Optional[str]:
    """Fetch a URL with exponential backoff retries. Returns HTML text, or
    None if all attempts fail (the caller decides whether that's fatal)."""
    headers = {"User-Agent": user_agent}

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            wait = backoff_base_seconds ** attempt
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {url}: {exc}. "
                f"Retrying in {wait}s..."
            )
            if attempt < max_retries:
                time.sleep(wait)
            else:
                logger.error(f"Giving up on {url} after {max_retries} attempts.")
    return None


def _parse_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def parse_page(html: str) -> List[Story]:
    """Parse a Hacker News front-page HTML document into Story records.

    HN renders each story as a `tr.athing` row immediately followed by a
    sibling `tr` containing the score/comments subtext. Job postings and a
    few edge cases lack a score or comment count, so both are optional.
    """
    soup = BeautifulSoup(html, "html.parser")
    stories: List[Story] = []

    story_rows = soup.select("tr.athing")
    logger.info(f"Found {len(story_rows)} story rows in page.")

    for row in story_rows:
        story_id = row.get("id")
        rank_text = row.select_one("span.rank")
        rank = _parse_int(rank_text.text) if rank_text else None

        title_link = row.select_one("span.titleline > a")
        if not title_link:
            logger.warning(f"Skipping row {story_id}: no title link found.")
            continue

        title = title_link.text.strip()
        url = title_link.get("href")

        site_bit = row.select_one("span.sitebit span.sitestr")
        domain = site_bit.text.strip() if site_bit else None

        subtext_row = row.find_next_sibling("tr")
        points = None
        comments = None
        if subtext_row:
            subtext = subtext_row.select_one("td.subtext")
            if subtext:
                score_span = subtext.select_one("span.score")
                points = _parse_int(score_span.text) if score_span else None

                comment_link = subtext.find_all("a")
                if comment_link:
                    last_link_text = comment_link[-1].text.strip()
                    if "comment" in last_link_text.lower():
                        comments = _parse_int(last_link_text)
                    elif last_link_text.lower() == "discuss":
                        comments = 0

        stories.append(Story(
            story_id=story_id,
            rank=rank if rank is not None else -1,
            title=title,
            url=url,
            domain=domain,
            points=points,
            comments=comments,
        ))

    return stories


def stories_to_dicts(stories: List[Story]) -> List[dict]:
    return [asdict(s) for s in stories]

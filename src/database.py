"""
database.py

Thin SQLite persistence layer. Every scrape run inserts a fresh snapshot
row per story (rather than overwriting), so the same story appearing on
the front page across multiple runs builds a time series of its rank,
points, and comment count — that history is what makes trend analysis
possible later.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List
from datetime import datetime, timezone

from scraper import Story


SCHEMA = """
CREATE TABLE IF NOT EXISTS story_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    story_id TEXT NOT NULL,
    rank INTEGER,
    title TEXT NOT NULL,
    url TEXT,
    domain TEXT,
    points INTEGER,
    comments INTEGER
);

CREATE INDEX IF NOT EXISTS idx_story_id ON story_snapshots(story_id);
CREATE INDEX IF NOT EXISTS idx_scraped_at ON story_snapshots(scraped_at);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_snapshot(conn: sqlite3.Connection, stories: List[Story]) -> int:
    """Insert one row per story for this scrape run. Returns rows inserted."""
    scraped_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (scraped_at, s.story_id, s.rank, s.title, s.url, s.domain, s.points, s.comments)
        for s in stories
    ]
    conn.executemany(
        """
        INSERT INTO story_snapshots
            (scraped_at, story_id, rank, title, url, domain, points, comments)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def get_story_history(conn: sqlite3.Connection, story_id: str) -> List[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM story_snapshots WHERE story_id = ? ORDER BY scraped_at",
        (story_id,),
    )
    return cursor.fetchall()


def get_latest_snapshot(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    latest_ts = conn.execute(
        "SELECT MAX(scraped_at) FROM story_snapshots"
    ).fetchone()[0]
    if latest_ts is None:
        return []
    cursor = conn.execute(
        "SELECT * FROM story_snapshots WHERE scraped_at = ? ORDER BY rank",
        (latest_ts,),
    )
    return cursor.fetchall()


def count_snapshots(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM story_snapshots").fetchone()[0]

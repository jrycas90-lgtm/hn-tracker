"""
analyze.py

Reads accumulated snapshots from the SQLite database and produces:
  - A printed table of the current top stories
  - A chart of points-over-time for whichever stories have the most
    history recorded (i.e. stories that have stuck around across runs)

Run this after the pipeline has executed at least a couple of times --
with only one snapshot there's no trend to show yet.

Usage:
    python scripts/analyze.py --db data/hn_tracker.db --output output/
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from database import get_latest_snapshot, count_snapshots


def load_all_snapshots(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM story_snapshots", conn)
    conn.close()
    df["scraped_at"] = pd.to_datetime(df["scraped_at"])
    return df


def print_latest_top_stories(db_path: str, n: int = 10) -> None:
    conn = sqlite3.connect(db_path)
    rows = get_latest_snapshot(conn)
    conn.close()

    if not rows:
        print("No data yet -- run the pipeline first (python src/pipeline.py).")
        return

    print(f"\nMost recent snapshot -- top {n} stories:\n")
    for row in rows[:n]:
        pts = row["points"] if row["points"] is not None else "-"
        cmts = row["comments"] if row["comments"] is not None else "-"
        print(f"  #{row['rank']:<3} [{pts:>4} pts, {cmts:>4} comments] {row['title']}")


def chart_most_tracked_stories(df: pd.DataFrame, output_path: Path, top_n: int = 5) -> bool:
    """Chart points-over-time for the N stories with the most snapshots
    (i.e. the ones that have appeared across the most pipeline runs)."""
    if df.empty:
        return False

    snapshot_counts = df.groupby("story_id").size().sort_values(ascending=False)
    if snapshot_counts.max() < 2:
        print("Not enough repeated snapshots yet to chart a trend "
              "(each story only has one data point so far). "
              "Run the pipeline again later to build history.")
        return False

    top_ids = snapshot_counts.head(top_n).index

    plt.figure(figsize=(10, 6))
    for story_id in top_ids:
        story_df = df[df["story_id"] == story_id].sort_values("scraped_at")
        title = story_df["title"].iloc[0]
        label = (title[:40] + "...") if len(title) > 40 else title
        plt.plot(story_df["scraped_at"], story_df["points"], marker="o", label=label)

    plt.xlabel("Time")
    plt.ylabel("Points")
    plt.title(f"Points Over Time -- Top {len(top_ids)} Most-Tracked Stories")
    plt.legend(fontsize=8, loc="upper left")
    plt.xticks(rotation=30, ha="right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze HN tracker data")
    parser.add_argument("--db", type=Path, default=Path("data/hn_tracker.db"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}. Run the pipeline first: "
              f"python src/pipeline.py")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    print_latest_top_stories(str(args.db))

    df = load_all_snapshots(str(args.db))
    chart_path = args.output / "points_over_time.png"
    made_chart = chart_most_tracked_stories(df, chart_path)
    if made_chart:
        print(f"\nSaved trend chart -> {chart_path}")

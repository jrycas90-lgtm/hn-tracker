# Hacker News Tracker — Scraper & Data Pipeline

A scheduled web scraper that tracks Hacker News front-page stories over time: rank, points, and comment count, stored in SQLite so trends (which stories are climbing, which are stalling) become queryable rather than a single snapshot.

This isn't just a one-off scraping script — it's a small pipeline with retry logic, structured logging, offline-testable parsing, and a scheduled job that runs automatically via GitHub Actions and commits its own data back to the repo.

## What it does

1. **Fetches** the Hacker News front page (with retries + exponential backoff for transient failures).
2. **Parses** each story's rank, title, URL, domain, points, and comment count with BeautifulSoup.
3. **Stores** a snapshot row per story per run in SQLite — so the same story appearing across multiple runs builds a time series.
4. **Logs** every run (successes, warnings, failures) to a rotating log file, not just stdout.
5. **Analyzes** accumulated history into a top-stories table and a points-over-time trend chart.
6. **Runs on a schedule automatically** via a GitHub Actions workflow — no server required.

## Project structure

```
hn-tracker/
├── .github/workflows/
│   └── scrape.yml            # scheduled GitHub Actions job (runs every 6 hours)
├── config/
│   └── settings.yaml         # base URL, retry/backoff settings, logging config
├── fixtures/
│   └── sample_hn_page.html   # saved HTML snapshot used for offline unit tests
├── src/
│   ├── scraper.py            # fetch (network) + parse (pure function) logic
│   ├── database.py           # SQLite schema + insert/query helpers
│   ├── pipeline.py           # orchestrates fetch -> parse -> store -> log
│   └── logger.py             # rotating file + console logging setup
├── scripts/
│   └── analyze.py            # reads the DB, prints top stories, charts trends
├── tests/
│   └── test_scraper.py       # 8 unit tests for the parser, run offline
├── data/                     # hn_tracker.db lives here (created on first run)
├── logs/                     # pipeline.log lives here (created on first run)
├── output/                   # generated charts land here
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/<your-username>/hn-tracker.git
cd hn-tracker
pip install -r requirements.txt
```

## Usage

Run the pipeline once manually:

```bash
python src/pipeline.py
```

This fetches the current front page, parses it, and inserts a snapshot into `data/hn_tracker.db`. Run it again later (an hour, a day) to start building history for the same stories.

Then analyze what's been collected:

```bash
python scripts/analyze.py --db data/hn_tracker.db --output output/
```

This prints the most recent top stories to the console and, once there's more than one snapshot for a given story, generates `output/points_over_time.png` charting how points changed across runs.

## Running it on a schedule

**Option A — GitHub Actions (recommended, no server needed).**
The included workflow at `.github/workflows/scrape.yml` runs the pipeline every 6 hours on GitHub's own infrastructure and commits the updated `data/hn_tracker.db` and `logs/pipeline.log` straight back to the repo. To enable it:
1. Push this repo to GitHub.
2. Go to the **Actions** tab and enable workflows if prompted.
3. That's it — it'll run on the cron schedule automatically, and you can also trigger it manually from the Actions tab (`workflow_dispatch`).

Edit the `cron` line in `scrape.yml` to change the frequency.

**Option B — your own machine.**
Use Windows Task Scheduler, `cron` (macOS/Linux), or the `schedule` Python package to call `python src/pipeline.py` on whatever interval you want.

## Design decisions worth calling out

- **Parsing is separated from fetching.** `parse_page()` in `scraper.py` takes raw HTML and returns data — no network calls inside it. That's what makes the parser testable offline against a saved fixture instead of hitting the live site (or breaking) every time tests run.
- **Retries with exponential backoff.** Network requests fail transiently all the time; `fetch_page()` retries a few times with increasing delay before giving up, and logs each attempt.
- **Snapshots, not overwrites.** Each run inserts new rows rather than updating existing ones, which is what makes trend analysis possible — you can watch a story's point count and rank change across runs instead of only ever seeing the latest state.
- **Respectful scraping.** A descriptive custom `User-Agent`, a delay between requests when paginating, and pulling only the public front page (no login walls, no bypassing rate limits) — see the note below.

## A note on scraping etiquette

This scrapes only public, unauthenticated HTML and adds a delay between requests. If you adapt this for another site, check its `robots.txt` and terms of service first, and keep request rates low — the goal of a project like this is to demonstrate engineering practice, not to hammer someone else's server.

## Running tests

```bash
pytest tests/
```

All 8 tests run against the saved HTML fixture in `fixtures/`, so they don't depend on network access or on Hacker News's markup staying identical between test runs.

## Possible extensions

- Track HN's "Show HN" or "Ask HN" sections separately
- Add a `--since` flag to `analyze.py` for date-range filtering
- Alert (email/Slack webhook) when a tracked story crosses a point threshold
- Swap SQLite for Postgres and deploy the dashboard with Streamlit

## Tech stack

Python, requests, BeautifulSoup4, SQLite, pandas, matplotlib, pytest, GitHub Actions

## License

MIT

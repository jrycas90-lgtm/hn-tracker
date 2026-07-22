"""
Unit tests for scraper.parse_page.

These run entirely offline against a saved HTML fixture, so they won't
break due to network issues and won't hammer the live site during CI runs.
"""

import sys
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from scraper import parse_page, _parse_int

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_hn_page.html"


@pytest.fixture
def sample_html():
    return FIXTURE_PATH.read_text()


def test_parses_expected_number_of_stories(sample_html):
    stories = parse_page(sample_html)
    assert len(stories) == 5


def test_parses_title_and_url(sample_html):
    stories = parse_page(sample_html)
    first = stories[0]
    assert first.title == "Rust adds an optional garbage collector"
    assert first.url == "https://example.com/rust-gc"
    assert first.domain == "example.com"


def test_parses_points_and_comments(sample_html):
    stories = parse_page(sample_html)
    first = stories[0]
    assert first.points == 412
    assert first.comments == 287


def test_parses_rank(sample_html):
    stories = parse_page(sample_html)
    assert stories[0].rank == 1
    assert stories[3].rank == 4


def test_ask_hn_style_post_has_no_domain(sample_html):
    stories = parse_page(sample_html)
    ask_hn = stories[2]
    assert ask_hn.domain is None
    assert ask_hn.url.startswith("item?id=")


def test_job_post_with_discuss_link_has_zero_comments_and_no_points(sample_html):
    stories = parse_page(sample_html)
    job_post = stories[4]
    assert job_post.points is None
    assert job_post.comments == 0


def test_parse_int_handles_none_and_empty():
    assert _parse_int(None) is None
    assert _parse_int("") is None
    assert _parse_int("412 points") == 412
    assert _parse_int("287\xa0comments") == 287


def test_empty_html_returns_empty_list():
    assert parse_page("<html><body></body></html>") == []

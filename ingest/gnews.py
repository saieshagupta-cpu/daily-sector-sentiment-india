"""Google News RSS — per-ticker scraper.

Google News exposes a free RSS endpoint that aggregates news from every
indexed publisher: Economic Times, Mint, Business Standard, NDTV Profit,
Moneycontrol, CNBC-TV18, Reuters India, Bloomberg Quint, Financial Express,
Business Today, Hindu BusinessLine, and so on. No auth, no API key.

We query it once per ticker with that ticker's best human-readable name,
restricted to the last 7 days. This gives the dashboard guaranteed
per-ticker coverage that Finnhub *would* have provided if its free tier
covered NSE.

Throttle: 0.5s between calls. ~240 candidates → ~2 min per refresh.
"""
from __future__ import annotations

import time
import urllib.parse
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ingest.types import Article

BASE = "https://news.google.com/rss/search"
TIMEOUT = 15


def _build_url(query: str, country: str = "IN", lang: str = "en") -> str:
    params = {
        "q": query,
        "hl": f"{lang}-{country}",
        "gl": country,
        "ceid": f"{country}:{lang}",
    }
    return f"{BASE}?{urllib.parse.urlencode(params)}"


def _parse_dt(entry) -> datetime:
    p = getattr(entry, "published_parsed", None) or entry.get("published_parsed")
    if p:
        try:
            return datetime(*p[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _source_title(entry) -> str:
    """Google News entries carry the publisher in entry.source.title."""
    src = entry.get("source")
    if isinstance(src, dict):
        return src.get("title", "") or ""
    return getattr(src, "title", "") if src is not None else ""


def fetch_for_ticker(ticker: str, name_query: str,
                     max_items: int = 10, days_back: int = 7) -> list[Article]:
    """Pull recent Google News results for one ticker / company name."""
    # `when:Nd` is Google News' inline date filter
    query = f'{name_query} stock when:{days_back}d'
    url = _build_url(query)
    parsed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
    out: list[Article] = []
    for entry in parsed.entries[:max_items]:
        link = entry.get("link", "") or ""
        title = entry.get("title", "") or ""
        if not title or not link:
            continue
        out.append(Article(
            source="gnews",
            source_outlet=_source_title(entry) or "Google News",
            headline=title,
            summary=entry.get("summary", "") or "",
            url=link,
            published_at=_parse_dt(entry),
            tickers=[ticker],
        ))
    return out


def fetch_for_tickers(tickers_with_names: Iterable[tuple[str, str]],
                      sleep_between: float = 0.5,
                      max_items_per_ticker: int = 10) -> list[Article]:
    """Bulk fetch with throttling. Input: iterable of (ticker, query) pairs."""
    all_articles: list[Article] = []
    items = list(tickers_with_names)
    for i, (ticker, name) in enumerate(items):
        try:
            arts = fetch_for_ticker(ticker, name, max_items=max_items_per_ticker)
            all_articles.extend(arts)
            if (i + 1) % 25 == 0:
                print(f"[gnews] {i + 1}/{len(items)}")
        except Exception as e:
            print(f"[gnews] {ticker}: {type(e).__name__}: {e}")
        if i < len(items) - 1:
            time.sleep(sleep_between)
    return all_articles

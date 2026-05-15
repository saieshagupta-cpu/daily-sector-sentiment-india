"""RSS feed bundle — free, no-auth headline pull.

Each feed contributes a stream of headlines/snippets. We don't try to be
exhaustive; instead we pick a curated bundle that maximises sector coverage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ingest.types import Article

# Curated bundle — Indian financial press. Each entry: (outlet_label, url, sector_hint).
FEEDS: list[tuple[str, str, str | None]] = [
    # General market / news wire
    ("Moneycontrol Business",     "https://www.moneycontrol.com/rss/business.xml", None),
    ("Moneycontrol Markets",      "https://www.moneycontrol.com/rss/MCtopnews.xml", None),
    ("Economic Times Markets",    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", None),
    ("Economic Times Stocks",     "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", None),
    ("Livemint Markets",          "https://www.livemint.com/rss/markets", None),
    ("Livemint Companies",        "https://www.livemint.com/rss/companies", None),
    ("Business Standard Markets", "https://www.business-standard.com/rss/markets-106.rss", None),
    ("Business Standard Companies","https://www.business-standard.com/rss/companies-101.rss", None),
    ("NDTV Profit",               "https://www.ndtvprofit.com/feed", None),
    ("ET Industry Auto",          "https://economictimes.indiatimes.com/industry/auto/rssfeeds/13352306.cms", None),
    ("ET Industry Banking",       "https://economictimes.indiatimes.com/industry/banking/finance/banking/rssfeeds/13358305.cms", "finance"),
    ("ET Industry Energy",        "https://economictimes.indiatimes.com/industry/energy/power/rssfeeds/13357361.cms", "energy"),
    ("ET Industry Healthcare",    "https://economictimes.indiatimes.com/industry/healthcare/biotech/rssfeeds/13358361.cms", "healthcare"),
]


def _parse_dt(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        v = getattr(entry, key, None) or entry.get(key)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def pull_feed(outlet: str, url: str) -> list[Article]:
    parsed = feedparser.parse(url)
    out: list[Article] = []
    for e in parsed.entries[:50]:
        url_e = e.get("link", "") or ""
        if not url_e:
            continue
        summary = e.get("summary", "") or e.get("description", "") or ""
        # Strip basic HTML
        if "<" in summary:
            import re
            summary = re.sub(r"<[^>]+>", "", summary)
        out.append(Article(
            source="sec_edgar" if "sec.gov" in url else "rss",
            source_outlet=outlet,
            headline=e.get("title", "") or "",
            summary=summary[:500],
            url=url_e,
            published_at=_parse_dt(e),
            tickers=[],
        ))
    return out


def pull_all(feeds: Iterable[tuple[str, str, str | None]] | None = None) -> list[Article]:
    feeds = list(feeds) if feeds is not None else FEEDS
    all_articles: list[Article] = []
    for outlet, url, _hint in feeds:
        try:
            arts = pull_feed(outlet, url)
            all_articles.extend(arts)
            print(f"[rss] {outlet}: {len(arts)} articles")
        except Exception as e:
            print(f"[rss] {outlet}: {type(e).__name__}: {e}")
    return all_articles

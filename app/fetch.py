from __future__ import annotations

import calendar
import html
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import feedparser
import httpx

from app.config import SHANGHAI, Source
from app.models import Candidate, candidate_id
from app.textutil import canonicalize_url, clean_html, title_key


LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (compatible; DailyInfoGap/1.0; personal RSS digest;"
    f" contact: {os.getenv('CONTACT_EMAIL', 'not-configured')})"
)


@dataclass
class SourceFetchResult:
    source: Source
    items: list[Candidate]
    error: str | None = None


def parse_feed(
    content: bytes,
    source: Source,
    now: datetime,
    window_hours: int = 36,
) -> list[Candidate]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Invalid feed: {parsed.bozo_exception}")

    cutoff = now - timedelta(hours=window_hours)
    future_limit = now + timedelta(hours=6)
    candidates: list[Candidate] = []
    for entry in parsed.entries[:80]:
        title = html.unescape(clean_html(entry.get("title", "")))
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        published_at = _entry_datetime(entry)
        if published_at is None:
            continue
        published_at = published_at.astimezone(timezone.utc)
        if published_at < cutoff or published_at > future_limit:
            continue

        summary = clean_html(entry.get("summary", ""))
        if not summary and entry.get("content"):
            summary = clean_html(entry["content"][0].get("value", ""))
        canonical = canonicalize_url(link)
        if not canonical:
            continue
        candidates.append(
            Candidate(
                id=candidate_id(source.id, canonical, title_key(title)),
                title=title[:300],
                summary=summary[:1200],
                url=canonical,
                source_id=source.id,
                source_name=source.name,
                category=source.category,
                published_at=published_at.astimezone(SHANGHAI),
                source_priority=source.priority,
            )
        )
    return candidates


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    return None


def fetch_source(
    source: Source,
    now: datetime,
    timeout_seconds: float = 20,
    retries: int = 2,
) -> SourceFetchResult:
    last_error = ""
    for attempt in range(retries + 1):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout_seconds,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                },
            ) as client:
                response = client.get(source.url)
                response.raise_for_status()
            items = parse_feed(response.content, source, now)
            LOGGER.info("%s: %d items", source.name, len(items))
            return SourceFetchResult(source=source, items=items)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(attempt + 1)
    LOGGER.warning("%s failed: %s", source.name, last_error)
    return SourceFetchResult(source=source, items=[], error=last_error)


def fetch_all(
    sources: Iterable[Source],
    now: datetime,
    max_workers: int = 6,
) -> list[SourceFetchResult]:
    source_list = list(sources)
    results: list[SourceFetchResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_source, source, now): source
            for source in source_list
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                LOGGER.exception("Unexpected source failure: %s", source.name)
                results.append(
                    SourceFetchResult(
                        source=source,
                        items=[],
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
    return sorted(results, key=lambda item: (item.source.category, -item.source.priority))


from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.analyzer import AnalysisResult, analyze
from app.config import CATEGORY_ORDER, CATEGORY_QUOTAS, SHANGHAI, Source
from app.dedupe import deduplicate
from app.fetch import SourceFetchResult, fetch_all
from app.models import Candidate
from app.textutil import title_key


LOGGER = logging.getLogger(__name__)


class CollectionUnavailableError(RuntimeError):
    """Raised when the network is not ready and every source fails."""


@dataclass
class CollectionResult:
    candidates: list[Candidate]
    source_results: list[SourceFetchResult]
    window_start: datetime


@dataclass
class PipelineResult:
    analysis: AnalysisResult
    collection: CollectionResult
    generated_at: datetime


def collect(
    sources: list[Source],
    now: datetime | None = None,
    seen_urls: set[str] | None = None,
    seen_titles: set[str] | None = None,
    window_hours: int = 36,
) -> CollectionResult:
    current = now or datetime.now(SHANGHAI)
    LOGGER.info("Fetching %d sources", len(sources))
    source_results = fetch_all(sources, current)
    if source_results and all(result.error for result in source_results):
        failures = sum(1 for result in source_results if result.error)
        raise CollectionUnavailableError(
            f"All {failures} sources failed; network may not be ready"
        )
    raw_candidates = [
        candidate
        for result in source_results
        for candidate in result.items
    ]
    LOGGER.info("Fetched %d candidate articles", len(raw_candidates))
    clusters = deduplicate(raw_candidates)
    LOGGER.info("Deduplication reduced candidates to %d", len(clusters))

    if seen_urls is not None or seen_titles is not None:
        ignored_urls = seen_urls or set()
        ignored_titles = seen_titles or set()
        clusters = [
            candidate
            for candidate in clusters
            if candidate.url not in ignored_urls
            and title_key(candidate.title) not in ignored_titles
        ]

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in clusters:
        grouped[candidate.category].append(candidate)
    selected: list[Candidate] = []
    for category in CATEGORY_ORDER:
        ranked = sorted(
            grouped[category],
            key=lambda item: (item.source_priority, item.published_at),
            reverse=True,
        )
        selected.extend(ranked[:35])
    LOGGER.info(
        "Selected candidate pool: %s",
        {category: len(grouped[category]) for category in CATEGORY_ORDER},
    )
    return CollectionResult(
        candidates=selected,
        source_results=source_results,
        window_start=current - timedelta(hours=window_hours),
    )


def run_pipeline(
    sources: list[Source],
    seen_urls: set[str] | None = None,
    seen_titles: set[str] | None = None,
    now: datetime | None = None,
) -> PipelineResult:
    collection = collect(
        sources,
        now=now,
        seen_urls=seen_urls,
        seen_titles=seen_titles,
    )
    if not collection.candidates:
        raise RuntimeError("No unseen candidates were collected")
    analysis = analyze(collection.candidates)
    return PipelineResult(
        analysis=analysis,
        collection=collection,
        generated_at=datetime.now(SHANGHAI),
    )


def expected_quota_text() -> str:
    return "、".join(
        f"{category} {CATEGORY_QUOTAS[category]}"
        for category in CATEGORY_ORDER
    )


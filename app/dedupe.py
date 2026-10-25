from __future__ import annotations

from app.models import Candidate, SourceRef
from app.textutil import title_similarity


CATEGORY_SPECIFICITY = {
    "ai": 3,
    "finance": 2,
    "tech": 1,
}


def deduplicate(candidates: list[Candidate], threshold: float = 0.82) -> list[Candidate]:
    clusters: list[list[Candidate]] = []
    for candidate in candidates:
        placed = False
        for cluster in clusters:
            if any(_same_story(candidate, existing, threshold) for existing in cluster):
                cluster.append(candidate)
                placed = True
                break
        if not placed:
            clusters.append([candidate])

    merged: list[Candidate] = []
    for cluster in clusters:
        cluster.sort(
            key=lambda item: (
                CATEGORY_SPECIFICITY.get(item.category, 0),
                item.source_priority,
                item.published_at,
            ),
            reverse=True,
        )
        primary = cluster[0]
        primary.related_sources = []
        seen_urls = {primary.url}
        for other in cluster[1:]:
            if other.url in seen_urls:
                continue
            primary.related_sources.append(
                SourceRef(
                    source_id=other.source_id,
                    source_name=other.source_name,
                    url=other.url,
                )
            )
            seen_urls.add(other.url)
        merged.append(primary)
    return merged


def _same_story(left: Candidate, right: Candidate, threshold: float) -> bool:
    if left.url == right.url:
        return True
    if left.category != right.category:
        return False
    return title_similarity(left.title, right.title) >= threshold


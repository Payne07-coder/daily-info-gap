from datetime import datetime, timezone

from app.dedupe import deduplicate
from app.models import Candidate
from app.textutil import canonicalize_url, title_key


def candidate(
    source_id: str,
    title: str,
    url: str,
    priority: int,
) -> Candidate:
    canonical = canonicalize_url(url)
    return Candidate(
        id=f"{source_id}-{title_key(title)}",
        title=title,
        summary="summary",
        url=canonical,
        source_id=source_id,
        source_name=source_id,
        category="ai",
        published_at=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
        source_priority=priority,
    )


def test_canonicalize_url_removes_tracking() -> None:
    assert (
        canonicalize_url("https://example.com/a/?utm_source=x&b=2&a=1#top")
        == "https://example.com/a?a=1&b=2"
    )


def test_deduplicate_keeps_primary_and_source_refs() -> None:
    primary = candidate(
        "official",
        "OpenAI launches a frontier reasoning model",
        "https://official.example/model",
        10,
    )
    secondary = candidate(
        "news",
        "OpenAI launches a frontier reasoning model",
        "https://news.example/model",
        5,
    )
    result = deduplicate([secondary, primary])

    assert len(result) == 1
    assert result[0].source_id == "official"
    assert [source.source_id for source in result[0].related_sources] == ["news"]


def test_deduplicate_prefers_specific_category() -> None:
    general = candidate(
        "general",
        "New AI model changes app development",
        "https://example.com/shared-story",
        9,
    )
    specific = candidate(
        "ai-feed",
        "New AI model changes app development",
        "https://example.com/shared-story",
        5,
    )
    general.category = "tech"
    result = deduplicate([general, specific])

    assert len(result) == 1
    assert result[0].category == "ai"


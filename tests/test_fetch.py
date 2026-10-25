from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Source
from app.fetch import parse_feed


def test_parse_feed_normalizes_and_filters_items() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_feed.xml"
    source = Source(
        id="sample",
        name="Sample",
        url="https://example.com/feed",
        category="ai",
        priority=8,
    )
    now = datetime(2026, 10, 25, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    items = parse_feed(fixture.read_bytes(), source, now)

    assert len(items) == 1
    assert items[0].title == "OpenAI releases a new test model"
    assert items[0].summary == "A new model was announced."
    assert items[0].url == "https://example.com/news/new-model?id=42"
    assert items[0].category == "ai"


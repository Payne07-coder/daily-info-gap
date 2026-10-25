import json
from datetime import datetime, timezone

from app.analyzer import _to_items, validate_analysis
from app.models import Candidate


def make_candidate(index: int, category: str) -> Candidate:
    return Candidate(
        id=f"candidate-{index}",
        title=f"Title {index}",
        summary="Summary",
        url=f"https://example.com/{index}",
        source_id=f"source-{index}",
        source_name=f"Source {index}",
        category=category,
        published_at=datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
        source_priority=8,
    )


def valid_item(candidate_id: str, category: str) -> dict[str, str]:
    return {
        "candidate_id": candidate_id,
        "category": category,
        "headline": "测试标题",
        "what_happened": "这是一个可核实的事实。",
        "why_it_matters": "这是基于事实的影响分析。",
        "impact": "可能影响未来的产品节奏。",
        "evidence": "信息来自官方来源。",
        "confidence": "已确认",
    }


def test_validate_analysis_accepts_valid_output() -> None:
    candidates = [make_candidate(1, "ai"), make_candidate(2, "finance")]
    raw = json.dumps(
        {
            "items": [
                valid_item("candidate-1", "ai"),
                valid_item("candidate-2", "finance"),
            ]
        }
    )
    assert validate_analysis(raw, candidates) == []
    items = _to_items(raw, candidates)
    assert [item.category for item in items] == ["ai", "finance"]


def test_validate_analysis_rejects_unknown_candidate_and_quota() -> None:
    candidates = [make_candidate(index, "ai") for index in range(6)]
    raw = json.dumps(
        {
            "items": [
                valid_item(f"candidate-{index}", "ai")
                for index in range(6)
            ]
            + [valid_item("missing", "ai")]
        }
    )
    errors = validate_analysis(raw, candidates)
    assert any("exceeds quota" in error for error in errors)
    assert any("not in candidate input" in error for error in errors)


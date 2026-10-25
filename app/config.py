from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "logs"
SHANGHAI = ZoneInfo("Asia/Shanghai")

CATEGORY_ORDER = ("ai", "finance", "tech")
CATEGORY_LABELS = {
    "ai": "AI",
    "finance": "金融",
    "tech": "科技",
}
CATEGORY_QUOTAS = {
    "ai": 5,
    "finance": 4,
    "tech": 3,
}
SOURCE_TABLE_ORDER = {
    "ai": 0,
    "finance": 1,
    "tech": 2,
}


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    category: str
    priority: int
    enabled: bool = True


def load_sources(path: Path | None = None) -> list[Source]:
    source_path = path or CONFIG_DIR / "sources.json"
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    sources = [Source(**entry) for entry in raw]
    enabled = [source for source in sources if source.enabled]
    if not enabled:
        raise ValueError("No enabled sources configured")

    seen_ids: set[str] = set()
    for source in enabled:
        if source.id in seen_ids:
            raise ValueError(f"Duplicate source id: {source.id}")
        if source.category not in CATEGORY_ORDER:
            raise ValueError(f"Unknown category for {source.id}: {source.category}")
        seen_ids.add(source.id)
    return enabled


def ensure_runtime_dirs() -> None:
    for path in (DATA_DIR, DATA_DIR / "tmp", DOCS_DIR / "data", LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


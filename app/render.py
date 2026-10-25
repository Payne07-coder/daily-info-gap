from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.config import DOCS_DIR
from app.models import DigestItem


def write_digest(
    digest_date: date,
    generated_at: datetime,
    window_start: datetime,
    items: list[DigestItem],
    source_health: dict[str, Any],
    status: str,
    docs_dir: Path | None = None,
) -> dict[str, Any]:
    root = docs_dir or DOCS_DIR
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    digest = {
        "schema_version": 1,
        "date": digest_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "window_start": window_start.isoformat(),
        "status": status,
        "source_health": source_health,
        "items": [item.as_dict() for item in items],
    }
    _atomic_write(data_dir / f"{digest_date.isoformat()}.json", digest)
    _atomic_write(data_dir / "latest.json", digest)
    _update_manifest(data_dir, digest_date)
    return digest


def load_latest(docs_dir: Path | None = None) -> dict[str, Any] | None:
    path = (docs_dir or DOCS_DIR) / "data" / "latest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _update_manifest(data_dir: Path, latest_date: date) -> None:
    path = data_dir / "manifest.json"
    dates: list[str] = []
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            dates = [
                value
                for value in previous.get("dates", [])
                if isinstance(value, str) and value[:10] != latest_date.isoformat()
            ]
        except (json.JSONDecodeError, OSError):
            dates = []
    dates.insert(0, latest_date.isoformat())
    dates = sorted(set(dates), reverse=True)[:30]
    digest_files = sorted(
        file.stem
        for file in data_dir.glob("20??-??-??.json")
        if file.stem[:4].isdigit()
    )
    for value in digest_files:
        if value not in dates and len(dates) < 30:
            dates.append(value)
    manifest = {
        "latest": latest_date.isoformat(),
        "dates": sorted(set(dates), reverse=True)[:30],
    }
    _atomic_write(path, manifest)


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_name = handle.name
    os.replace(temporary_name, path)


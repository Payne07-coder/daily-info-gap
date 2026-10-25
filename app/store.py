from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

from app.config import DATA_DIR
from app.fetch import SourceFetchResult
from app.models import Candidate, DigestItem
from app.textutil import title_key


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "state.sqlite"
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS delivered (
                item_id TEXT PRIMARY KEY,
                delivered_date TEXT NOT NULL,
                title_key TEXT NOT NULL,
                canonical_url TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_delivered_title
                ON delivered(title_key);
            CREATE INDEX IF NOT EXISTS idx_delivered_date
                ON delivered(delivered_date);

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS source_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                checked_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            );
            """
        )
        self.connection.commit()

    def begin_run(self, started_at: datetime) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs(started_at, status) VALUES (?, 'running')",
            (started_at.isoformat(),),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        finished_at: datetime,
        item_count: int = 0,
        message: str = "",
    ) -> None:
        self.connection.execute(
            """
            UPDATE runs
            SET finished_at = ?, status = ?, item_count = ?, message = ?
            WHERE id = ?
            """,
            (finished_at.isoformat(), status, item_count, message[:2000], run_id),
        )
        self.connection.commit()

    def record_source_status(
        self,
        run_id: int,
        results: list[SourceFetchResult],
        checked_at: datetime,
    ) -> None:
        rows = [
            (
                run_id,
                result.source.id,
                result.source.name,
                "failed" if result.error else "ok",
                len(result.items),
                result.error,
                checked_at.isoformat(),
            )
            for result in results
        ]
        self.connection.executemany(
            """
            INSERT INTO source_status(
                run_id, source_id, source_name, status, item_count, error, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.connection.commit()

    def unseen(self, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        seen_urls = {
            row["canonical_url"]
            for row in self.connection.execute(
                "SELECT canonical_url FROM delivered"
            )
        }
        seen_titles = {
            row["title_key"]
            for row in self.connection.execute("SELECT title_key FROM delivered")
        }
        return [
            candidate
            for candidate in candidates
            if candidate.url not in seen_urls
            and title_key(candidate.title) not in seen_titles
        ]

    def seen_markers(self) -> tuple[set[str], set[str]]:
        urls = {
            row["canonical_url"]
            for row in self.connection.execute(
                "SELECT canonical_url FROM delivered"
            )
        }
        titles = {
            row["title_key"]
            for row in self.connection.execute("SELECT title_key FROM delivered")
        }
        return urls, titles

    def mark_delivered(
        self,
        items: list[DigestItem],
        delivered_date: date,
        created_at: datetime,
    ) -> None:
        rows = []
        for item in items:
            primary = item.sources[0]
            rows.append(
                (
                    item.id,
                    delivered_date.isoformat(),
                    title_key(item.headline),
                    primary.url,
                    created_at.isoformat(),
                )
            )
        with self.transaction():
            self.connection.executemany(
                """
                INSERT OR IGNORE INTO delivered(
                    item_id, delivered_date, title_key, canonical_url, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def cleanup_delivered(self, reference_date: date, keep_days: int = 30) -> None:
        cutoff = (reference_date - timedelta(days=keep_days)).isoformat()
        self.connection.execute(
            "DELETE FROM delivered WHERE delivered_date < ?",
            (cutoff,),
        )
        self.connection.commit()

    def latest_run(self) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


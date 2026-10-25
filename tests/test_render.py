from datetime import date, datetime

from app.render import write_digest


def test_write_digest_creates_latest_and_manifest(tmp_path) -> None:
    wrote = write_digest(
        digest_date=date(2026, 10, 25),
        generated_at=datetime.fromisoformat("2026-10-25T06:40:00+08:00"),
        window_start=datetime.fromisoformat("2026-10-24T18:40:00+08:00"),
        items=[],
        source_health={"ok": 1, "failed": 0, "failed_sources": []},
        status="ok",
        docs_dir=tmp_path,
    )
    assert wrote["date"] == "2026-10-25"
    assert (tmp_path / "data" / "latest.json").exists()
    assert (tmp_path / "data" / "2026-10-25.json").exists()
    manifest = (tmp_path / "data" / "manifest.json").read_text(encoding="utf-8")
    assert "2026-10-25" in manifest


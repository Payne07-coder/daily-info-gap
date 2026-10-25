import subprocess

import pytest

from app.publisher import PublishError, publish_site


def git(root, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_publish_without_remote_fails_after_local_commit(tmp_path) -> None:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text("test", encoding="utf-8")

    with pytest.raises(PublishError, match="remote 'origin'"):
        publish_site(tmp_path)

    assert git(tmp_path, "log", "-1", "--pretty=%s") == "Update daily information digest"


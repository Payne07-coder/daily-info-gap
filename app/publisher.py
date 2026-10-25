from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.config import PROJECT_ROOT


LOGGER = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


def publish_site(root: Path | None = None) -> bool:
    project = root or PROJECT_ROOT
    _git(project, "add", "docs")
    diff = subprocess.run(
        ["git", "-C", str(project), "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode == 0:
        LOGGER.info("No static site changes to publish")
        return False
    if diff.returncode != 1:
        raise PublishError(diff.stderr.strip() or "Unable to inspect Git changes")

    message = "Update daily information digest"
    _git(project, "commit", "-m", message)
    remote = subprocess.run(
        ["git", "-C", str(project), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        raise PublishError(
            "Git remote 'origin' is not configured; static site was generated locally"
        )
    _git(project, "push", "origin", "HEAD")
    LOGGER.info("Published static site to %s", remote.stdout.strip())
    return True


def has_remote(root: Path | None = None) -> bool:
    project = root or PROJECT_ROOT
    result = subprocess.run(
        ["git", "-C", str(project), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _git(project: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PublishError(detail or f"Git command failed: {' '.join(args)}")


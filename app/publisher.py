from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from app.config import PROJECT_ROOT


LOGGER = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


def publish_site(root: Path | None = None) -> bool:
    project = root or PROJECT_ROOT
    git = _git_executable()
    _git(project, "add", "docs")
    diff = subprocess.run(
        [git, "-C", str(project), "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        env=_git_environment(),
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
        [git, "-C", str(project), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        env=_git_environment(),
        check=False,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        raise PublishError(
            "Git remote 'origin' is unavailable: "
            + (remote.stderr.strip() or remote.stdout.strip() or "unknown Git error")
        )
    _git(project, "-c", "credential.interactive=false", "push", "origin", "HEAD")
    LOGGER.info("Published static site to %s", remote.stdout.strip())
    return True


def has_remote(root: Path | None = None) -> bool:
    project = root or PROJECT_ROOT
    git = _git_executable()
    result = subprocess.run(
        [git, "-C", str(project), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        env=_git_environment(),
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def push_current(root: Path | None = None) -> None:
    project = root or PROJECT_ROOT
    _git(
        project,
        "-c",
        "credential.interactive=false",
        "push",
        "origin",
        "HEAD",
    )


def _git(project: Path, *args: str) -> None:
    git = _git_executable()
    completed = subprocess.run(
        [git, "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_git_environment(),
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PublishError(detail or f"Git command failed: {' '.join(args)}")


def _git_executable() -> str:
    bundled = Path("D:/Agent/Git/cmd/git.exe")
    if bundled.is_file():
        return str(bundled)
    found = shutil.which("git")
    if found:
        return found
    raise PublishError("Git executable not found")


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "never"
    environment["GCM_CREDENTIAL_STORE"] = "wincredman"
    return environment


from __future__ import annotations

import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())


"""Load `.env` from the project tree into ``os.environ`` (stdlib only).

Python does not read ``.env`` files automatically. We walk upward from the
current working directory (and from this package) so ``OPENROUTER_API_KEY`` in
``.env`` works for CLI runs and ``audit()`` calls without manual ``export``.
Existing environment variables are never overwritten.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv() -> Path | None:
    """Load the first ``.env`` found; return its path or ``None``."""
    for directory in _search_directories():
        path = directory / ".env"
        if not path.is_file():
            continue
        _apply_file(path)
        return path
    return None


def _search_directories() -> list[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(resolved)

    add(Path.cwd())
    here = Path(__file__).resolve().parent
    for parent in (here, *here.parents):
        add(parent)
    return candidates


def _apply_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value

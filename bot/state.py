"""Load/save bot state (state.json, lives on the orphan `bot-state` branch on
GitHub -- see docs/BOT.md). Schema per CLAUDE.md section 8.3; Phase 1 only reads
and writes `seen`, the rest exists so later phases don't need a migration.

Written atomically (temp file + rename) so a crash mid-write can never leave a
half-written state.json for the next run to choke on.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

SEEN_CAP = 500


def empty() -> dict:
    return {
        "seen": [],
        "pending": {},
        "posted": {},
        "approved_queue": [],
        "failed": {},
        "daily": {"date": "", "published": 0},
    }


def load(path: str | Path) -> dict:
    """Tolerates a missing or corrupt file by starting empty -- never raises, and
    never re-triggers posting history (first-run seeding is the caller's job)."""
    path = Path(path)
    if not path.exists():
        return empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return empty()
    if not isinstance(data, dict):
        return empty()
    state = empty()
    state.update({k: v for k, v in data.items() if k in state})
    return state


def save(path: str | Path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def is_seen(state: dict, key: str) -> bool:
    return key in state.get("seen", [])


def mark_seen(state: dict, key: str) -> None:
    seen = state.setdefault("seen", [])
    if key in seen:
        return
    seen.append(key)
    if len(seen) > SEEN_CAP:
        del seen[: len(seen) - SEEN_CAP]

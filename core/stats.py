"""Activity counters (counts only: no user ids, no messages, no inputs).

Stats are *non-critical*: nothing in here may ever break a command. Every
failure is logged and swallowed, and the bot keeps working without a file.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

log = logging.getLogger(__name__)

SCHEMA = 1
_KEY_MAX = 64


def _nonneg_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected a non-negative integer")
    return value


def _nonneg_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("expected a non-negative number")
    return float(value)


def _clean_counter(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict) or len(raw) > config.MAX_STATS_KEYS:
        raise ValueError("bad counter")
    out: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or len(key) > _KEY_MAX:
            raise ValueError("bad counter key")
        out[key] = _nonneg_int(value)
    return out


class StatsStore:
    """Lifetime counters (saved to a JSON file) plus per-session counters."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data = self._fresh()
        self._dirty = False
        self._warned = False
        self.last_save_ok: bool | None = None  # None = never tried
        self._session_commands: dict[str, int] = {}
        self._session_runs = 0
        self._session_errors = 0
        self.session_started = time.monotonic()

    # ---- persistence -------------------------------------------------------
    @staticmethod
    def _fresh() -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "first_started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sessions": 0,
            "commands": {},
            "algos": {},
            "runs_total": 0,
            "runs_failed": 0,
            "user_errors": 0,
            "errors": {},
            "render_ms_total": 0.0,
            "render_ms_count": 0,
            "render_ms_max": 0.0,
        }

    def _sanitize(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
            raise ValueError("unknown stats schema")
        data = self._fresh()
        for key in ("sessions", "runs_total", "runs_failed", "user_errors", "render_ms_count"):
            data[key] = _nonneg_int(raw.get(key, 0))
        for key in ("render_ms_total", "render_ms_max"):
            data[key] = _nonneg_float(raw.get(key, 0.0))
        first = raw.get("first_started")
        if isinstance(first, str) and len(first) <= 40:
            data["first_started"] = first
        for key in ("commands", "algos", "errors"):
            data[key] = _clean_counter(raw.get(key, {}))
        return data

    def load(self) -> None:
        """Read the stats file. Missing = fresh start; damaged = quarantined, fresh start."""
        if self._path is None:
            return
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            log.warning("stats file unreadable (%s); using memory only", exc)
            return
        try:
            data = self._sanitize(json.loads(text))
        except (ValueError, TypeError) as exc:
            log.error("stats file damaged (%s); starting fresh", exc)
            with contextlib.suppress(OSError):
                os.replace(self._path, self._path.with_name(self._path.name + ".corrupt"))
            return
        with self._lock:
            self._data = data

    def save(self) -> bool:
        """Atomic write (temp file + rename). Returns False if it could not save."""
        if self._path is None:
            return False
        with self._lock:
            if not self._dirty:
                return self.last_save_ok is not False
            payload = json.dumps(self._data, sort_keys=True)
            self._dirty = False
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            with self._lock:
                self._dirty = True
            self.last_save_ok = False
            if not self._warned:
                log.warning("could not save stats (%s); will keep retrying quietly", exc)
                self._warned = True
            return False
        self.last_save_ok = True
        self._warned = False
        return True

    # ---- recording ---------------------------------------------------------
    @staticmethod
    def _bump(counter: dict[str, int], key: str) -> None:
        key = key[:_KEY_MAX]
        if key not in counter and len(counter) >= config.MAX_STATS_KEYS:
            key = "other"
        counter[key] = counter.get(key, 0) + 1

    def start_session(self) -> None:
        with self._lock:
            self._data["sessions"] += 1
            self._dirty = True
        self.session_started = time.monotonic()

    def record_command(self, name: str) -> None:
        with self._lock:
            self._bump(self._data["commands"], name)
            self._bump(self._session_commands, name)
            self._dirty = True

    def record_run(self, algo: str, elapsed_ms: float = 0.0, *, ok: bool = True) -> None:
        with self._lock:
            self._data["runs_total"] += 1
            self._session_runs += 1
            if ok:
                self._bump(self._data["algos"], algo)
                ms = max(float(elapsed_ms), 0.0)
                self._data["render_ms_total"] += ms
                self._data["render_ms_count"] += 1
                self._data["render_ms_max"] = max(self._data["render_ms_max"], ms)
            else:
                self._data["runs_failed"] += 1
            self._dirty = True

    def record_error(self, kind: str, *, user: bool = False) -> None:
        """`user=True` for bad input (not our fault); otherwise an unexpected failure."""
        with self._lock:
            if user:
                self._data["user_errors"] += 1
            else:
                self._bump(self._data["errors"], kind)
                self._session_errors += 1
            self._dirty = True

    # ---- reading -----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            lifetime = deepcopy(self._data)
            session = {
                "commands": dict(self._session_commands),
                "runs": self._session_runs,
                "errors": self._session_errors,
                "seconds": time.monotonic() - self.session_started,
            }
        count = lifetime["render_ms_count"]
        lifetime["render_ms_avg"] = lifetime["render_ms_total"] / count if count else 0.0
        return {"lifetime": lifetime, "session": session}

    @staticmethod
    def top(counter: dict[str, int], n: int = 5) -> list[tuple[str, int]]:
        """Highest counts first; ties broken alphabetically so output is stable."""
        return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:n]

    @property
    def path(self) -> Path | None:
        return self._path

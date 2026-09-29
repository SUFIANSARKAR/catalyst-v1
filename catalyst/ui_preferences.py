"""Persistent UI preferences for the Catalyst application.

Preferences are deliberately presentation-only. They never contain provider
secrets or model API keys. The store is a tiny JSON document with atomic writes
so the UI can persist avatar appearance, motion, voice, and layout choices
across browser sessions/devices without coupling them to the AI brain.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "motion": "full",
    "voice_auto": False,
    "live_auto": False,
    "compact_mode": False,
    "show_activity": True,
    "use_memory": True,
    "confirm_actions": True,
    "keep_session": True,
    "appearance": "signature",
    "avatar_expression": "neutral",
    "avatar_stage": "presence",
}


class UIPreferences:
    def __init__(self, path: str | Path = "catalyst_data/ui_preferences.json") -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, ValueError, TypeError):
            raw = {}
        out = dict(DEFAULTS)
        if isinstance(raw, dict):
            out.update({k: v for k, v in raw.items() if k in DEFAULTS})
        return out

    def get(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._read()
            for key, value in changes.items():
                if key in DEFAULTS:
                    current[key] = value
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
            temp.replace(self.path)
            return current


__all__ = ["DEFAULTS", "UIPreferences"]

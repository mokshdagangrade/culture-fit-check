"""Shared, validated age windows. Importing this module never calls an API."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

DEFAULT_WINDOWS_PATH = Path(__file__).with_name("signal_windows.json")
SOURCES = frozenset({"weather", "news", "social", "trends", "attention", "youtube", "sports", "events", "calendar"})


@dataclass(frozen=True)
class SignalWindow:
    lookback_days: int
    lookahead_days: int

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{key} must be a non-negative integer")

    def bounds(self, reference_date: date) -> tuple[date, date]:
        return (reference_date - timedelta(days=self.lookback_days),
                reference_date + timedelta(days=self.lookahead_days))


def load_windows(path: str | Path = DEFAULT_WINDOWS_PATH) -> dict[str, SignalWindow]:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or set(data) != SOURCES:
        raise ValueError(f"Window settings must contain exactly: {', '.join(sorted(SOURCES))}")
    windows = {}
    for source, values in data.items():
        if not isinstance(values, dict):
            raise ValueError(f"{source}: expected an object of window settings")
        try:
            windows[source] = SignalWindow(**values)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source}: {exc}") from exc
    return windows


def window_settings(windows: dict[str, SignalWindow]) -> dict:
    return {source: asdict(window) for source, window in windows.items()}

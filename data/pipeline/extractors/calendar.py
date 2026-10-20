"""Fetch and cache a country calendar once per year, then split by location."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from http_client import polite_get
from schemas import CalendarDoc, Holiday, SourceMeta, GeoTag
from signal_windows import SignalWindow
from us_states import US_STATES

BASE_URL = "https://calendarific.com/api/v2/holidays"
CACHE_DIR = Path(__file__).resolve().parents[1] / "out" / "cache" / "calendarific"
_STATE_NAMES = {s["name"].casefold(): s["code"] for s in US_STATES}
_STATE_CODES = {s["code"] for s in US_STATES}


class MissingAPIKey(Exception):
    pass


def holiday_locations(raw: dict) -> tuple[bool, list[str]]:
    """Use explicit locations, never holiday type or observed state coverage.

    Unknown or missing locations are errors. US territories are recognised but
    omitted from the current 50-state scope.
    """
    states, locations = raw.get("states"), raw.get("locations")
    if isinstance(states, str) and states.strip().casefold() == "all":
        return True, []
    if isinstance(locations, str) and locations.strip().casefold() == "all":
        return True, []
    if isinstance(states, list) and states:
        tokens = [(s.get("iso") or s.get("abbrev") or s.get("name"))
                  if isinstance(s, dict) else s for s in states]
    elif isinstance(locations, str) and locations.strip():
        tokens = locations.split(",")
    elif isinstance(states, str) and states.strip():
        tokens = states.split(",")
    else:
        raise ValueError(f"Holiday has no usable location: {raw.get('name')!r}")
    codes = set()
    for token in tokens:
        if not isinstance(token, str):
            raise ValueError(f"Invalid holiday location: {token!r}")
        value = token.strip()
        code = _STATE_NAMES.get(value.casefold(), value.upper().removeprefix("US-"))
        if code in _STATE_CODES:
            codes.add(code)
        elif code not in {"DC", "PR", "GU", "VI", "AS", "MP", "UM"}:
            raise ValueError(f"Unrecognised holiday location: {token!r}")
    return False, sorted(codes)


def _read_year(year, cache_dir, cache_days, refresh, timeout):
    cache_file = Path(cache_dir) / f"US_{year}.json"
    now = datetime.now(timezone.utc)
    if not refresh and cache_file.exists():
        cached = json.loads(cache_file.read_text())
        age = now - datetime.fromisoformat(cached["fetched_at"])
        if timedelta(0) <= age < timedelta(days=cache_days):
            return cached

    api_key = os.environ.get("CALENDARIFIC_API_KEY")
    if not api_key:
        raise MissingAPIKey("Set CALENDARIFIC_API_KEY, or provide a fresh cached country calendar.")
    response = polite_get(BASE_URL, params={"api_key": api_key, "country": "US", "year": year}, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if body.get("meta", {}).get("code") != 200:
        raise ValueError("Calendarific returned an unsuccessful response")
    holidays = body.get("response", {}).get("holidays")
    if not isinstance(holidays, list):
        raise ValueError("Calendarific response.holidays must be a list")
    cached = {"fetched_at": now.isoformat(), "holidays": holidays}
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    temp = cache_file.with_suffix(".tmp")
    temp.write_text(json.dumps(cached, ensure_ascii=False))
    temp.replace(cache_file)
    return cached


def fetch_calendar_batch(states, reference_date=None, window=None, cache_dir=CACHE_DIR,
                         cache_days=30, refresh=False, timeout=10):
    """Return state calendars and one national calendar; at most one call/year.

    Cached full-year responses allow changing windows without another API call.
    The returned lists are bounded by the requested inclusive calendar dates.
    """
    reference_date = reference_date or date.today()
    window = window or SignalWindow(21, 30)
    if type(cache_days) is not int or cache_days < 1:
        raise ValueError("cache_days must be a positive integer")
    start, end = window.bounds(reference_date)
    by_state = {s["code"]: [] for s in states}
    national, fetched, urls = [], [], []
    for year in range(start.year, end.year + 1):
        cached = _read_year(year, cache_dir, cache_days, refresh, timeout)
        fetched.append(datetime.fromisoformat(cached["fetched_at"]))
        urls.append(f"{BASE_URL}?country=US&year={year}")
        for raw in cached["holidays"]:
            day = date.fromisoformat(raw["date"]["iso"][:10])
            if not start <= day <= end:
                continue
            is_national, codes = holiday_locations(raw)
            types = raw.get("type") or []
            holiday = Holiday(name=raw["name"], date=day.isoformat(), type=types[0] if types else None,
                              state_specific=not is_national, is_national=is_national)
            if is_national:
                national.append(holiday)
            else:
                notes = {}
                for entry in raw.get("states", []) if isinstance(raw.get("states"), list) else []:
                    if isinstance(entry, dict) and entry.get("exception"):
                        for code in holiday_locations({"states": [entry]})[1]:
                            notes[code] = entry["exception"]
                for code in codes:
                    if code in by_state:
                        by_state[code].append(
                            holiday.model_copy(update={"observance_note": notes[code]}) if code in notes else holiday)
    # The oldest contributing fetch is conservative when two years were cached separately.
    meta = SourceMeta(source="calendarific", url=";".join(urls), fetched_at=min(fetched))
    calendars = {}
    for code, holidays in by_state.items():
        calendars[code] = CalendarDoc(
            state_code=code, date=reference_date, meta=meta.model_copy(update={"status": "ok" if holidays else "empty"}),
            geo=GeoTag(scope="state", state_code=code, confidence="exact"),
            holidays_today=[h for h in holidays if h.date == reference_date.isoformat()],
            holidays_this_month=holidays,  # legacy field name; now covers the configured window
        )
    shared = {"country_code": "US", "date": reference_date.isoformat(),
              "meta": meta.model_copy(update={"status": "ok" if national else "empty"}).model_dump(mode="json"),
              "geo": {"scope": "national", "confidence": "exact"},
              "holidays_today": [h.model_dump(mode="json") for h in national if h.date == reference_date.isoformat()],
              "holidays_this_month": [h.model_dump(mode="json") for h in national]}
    return calendars, shared

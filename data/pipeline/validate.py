from collections import Counter
from datetime import datetime, timezone

from us_states import US_STATES, STATE_CODES

US_LAT_RANGE = (18.0, 72.0)     # covers Hawaii to northern Alaska
US_LON_RANGE = (-180.0, -65.0)  # covers Alaska's westward extent to the East Coast


def check_reference_data() -> list[str]:
    """Sanity-check us_states.py itself. Run once, independent of any API call."""
    errors = []
    seen_codes = set()
    for s in US_STATES:
        if s["code"] in seen_codes:
            errors.append(f"duplicate state code: {s['code']}")
        seen_codes.add(s["code"])

        if not (US_LAT_RANGE[0] <= s["lat"] <= US_LAT_RANGE[1]):
            errors.append(f"{s['code']}: latitude {s['lat']} outside expected US range")
        if not (US_LON_RANGE[0] <= s["lon"] <= US_LON_RANGE[1]):
            errors.append(f"{s['code']}: longitude {s['lon']} outside expected US range")

    if seen_codes != STATE_CODES:
        errors.append("US_STATES and STATE_CODES are out of sync")
    if len(US_STATES) != 50:
        errors.append(f"expected 50 states, found {len(US_STATES)}")
    return errors


def check_batch(stitched_docs: list, expected_date) -> dict:
    """
    stitched_docs: list of schemas.StitchedDoc already built by stitch.py.
    Returns a report; does not raise, so callers can decide what a
    partial run means (e.g. rerun just the missing states).
    """
    report = {"errors": [], "warnings": [], "coverage": {}}

    codes_seen = [d.state_code for d in stitched_docs]
    counts = Counter(codes_seen)

    duplicates = [code for code, n in counts.items() if n > 1]
    if duplicates:
        report["errors"].append(f"duplicate state(s) in batch: {duplicates}")

    missing_states = STATE_CODES - set(codes_seen)
    if missing_states:
        report["warnings"].append(f"missing {len(missing_states)} state(s): {sorted(missing_states)}")

    wrong_date = [d.state_code for d in stitched_docs if d.date != expected_date]
    if wrong_date:
        report["errors"].append(f"document(s) not dated {expected_date}: {wrong_date}")

    source_missing_counts = Counter()
    for d in stitched_docs:
        for src in d.sources_missing:
            source_missing_counts[src] += 1
    report["coverage"] = {
        "states_processed": len(stitched_docs),
        "states_expected": len(STATE_CODES),
        "missing_by_source": dict(source_missing_counts),
    }

    now = datetime.now(timezone.utc)
    stale = []
    for d in stitched_docs:
        for src_name in ("weather", "news", "trends", "attention", "calendar", "social", "sports"):
            src_doc = getattr(d.signals, src_name)
            if src_doc is not None and (now - src_doc.meta.fetched_at).total_seconds() > 3600:
                stale.append((d.state_code, src_name))
    if stale:
        report["warnings"].append(f"fetched over an hour before validation ran: {stale}")

    report["ok"] = len(report["errors"]) == 0
    return report

"""
Builds a manual review set for the retrieval pipeline.

The app's own history exporter only covers campaigns somebody actually ran.
To measure retrieval you need coverage you choose: a grid of brands, states
and briefs, with the candidates the ranker saw, labelled by hand.

    python training/make_retrieval_review.py \
        --parquet /path/to/clean/signal_candidate.parquet \
        --brands  /path/to/brandvoice_briefs.parquet \
        --out-dir training/out/review-01

Writes three files:

  review.csv    what a human labels. 300 rows by default. Model scores are
                NOT in it and candidate order is shuffled, so the reviewer
                cannot anchor on what the ranker thought.
  model.jsonl   the withheld half: per-row model score, reason, rank, and the
                pool metadata. Joined back by row_id when scoring.
  overlap.csv   a slice of review.csv for a second reviewer, so inter-rater
                agreement has something to be computed on.

Fill in `usable`, `would_use_first`, `notes` and `reviewer` in review.csv,
then run score_retrieval_review.py.

Rows include a few the safety gate refused (marked `gate=refused`), which is
how the guardrail's false-positive rate becomes measurable: a refused signal
a human also calls unusable is a correct refusal.
"""

import argparse
import csv
import json
import os
import random
import sys
import types
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

DEFAULT_BRIEFS = [
    "Launch a new seasonal product this week.",
    "Drive weekend footfall to physical locations.",
    "Re-engage customers who have not bought in three months.",
    "Announce a feature or menu change customers have asked for.",
    "Build local awareness in a market where the brand is new.",
    "Promote a limited-time discount without cheapening the brand.",
]

# Spread states across census regions rather than sampling 50 at random, so
# a 30-cell review is not accidentally all Sun Belt.
DEFAULT_STATES = [
    "California", "Washington", "Arizona",          # West
    "Texas", "Florida", "Georgia",                  # South
    "Illinois", "Ohio", "Minnesota",                # Midwest
    "New York", "Massachusetts", "Pennsylvania",    # Northeast
]

REVIEW_FIELDS = [
    # context the reviewer needs
    "row_id", "sample_id", "state", "brand", "industry", "brief",
    "source", "geo", "gate", "signal_text", "signal_context",
    # what the reviewer fills in
    "usable", "would_use_first", "notes", "reviewer",
]

USABLE_GUIDE = "0=unusable, 1=plausible stretch, 2=would use"


class ParquetCollection:
    """
    Minimal stand-in for the Mongo collection, so the review set is built by
    the same candidate_service code the app runs rather than a reimplementation
    of its filters. Supports only the query shape candidate_service issues.
    """

    def __init__(self, rows: list[dict]):
        self.rows = rows

    def find(self, query: dict, projection=None):
        date_range = query.get("date", {})
        lo, hi = date_range.get("$gte"), date_range.get("$lte")
        wanted = {clause.get("state_code") for clause in query.get("$or", [])}
        wanted.discard(None)
        flags = {k: v for k, v in query.items()
                 if k in ("is_dup", "is_noise", "is_within_window")}

        matched = []
        for row in self.rows:
            if lo and not (lo <= str(row.get("date")) <= hi):
                continue
            if wanted and not (row.get("state_code") in wanted or row.get("is_national")):
                continue
            if any(bool(row.get(key)) != value for key, value in flags.items()):
                continue
            matched.append(dict(row))
        return _Sortable(matched)


class _Sortable:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, spec):
        for key, direction in reversed(spec):
            self.rows.sort(key=lambda r: (r.get(key) is None, r.get(key)),
                           reverse=direction < 0)
        return self.rows


def load_candidates(path: Path) -> list[dict]:
    import pandas as pd

    frame = pd.read_parquet(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    for flag in ("is_national", "is_dup", "is_noise", "is_within_window"):
        if flag in frame:
            frame[flag] = frame[flag].fillna(False).astype(bool)
    frame = frame.astype(object).where(frame.notna(), None)
    return frame.to_dict("records")


def load_brands(path: Path, limit: int) -> list[dict]:
    import pandas as pd

    frame = pd.read_parquet(path)
    if "task" in frame:
        frame = frame[frame["task"] == "write"]      # drop the 296 craft rows
    brands = []
    for brand, group in frame.groupby("brand"):
        first = group.iloc[0]
        brands.append({
            "name": brand,
            "industry": first.get("category"),
            "brand_voice": first.get("voice_summary"),
            "description": first.get("voice_summary"),
            "products": None,
            "target_audience": None,
        })
    brands.sort(key=lambda b: b["name"])
    return brands[:limit] if limit else brands


def normalise(text) -> str:
    return " ".join(str(text or "").split()).casefold()


def pick_candidates(pool: list, refused: list, per_cell: int, refused_per_cell: int,
                    rng: random.Random, seen: dict | None = None,
                    max_repeats: int = 1) -> list[dict]:
    """
    A source-spread slice of the pool, plus a few refused signals.

    `seen` counts how often each distinct signal has already been put in front
    of a reviewer across the whole run, and `max_repeats` caps it. Without this
    the national sources dominate: attention has 20 rows and sports 84 for the
    entire country, so the same Wikipedia article and the same NFL game land in
    all 50 states' pools and a 300-row review spends 40% of its budget
    re-judging four signals.
    """
    seen = seen if seen is not None else {}

    def take(item: dict, gate: str) -> dict | None:
        key = normalise(item.get("text"))
        if not key or seen.get(key, 0) >= max_repeats:
            return None
        seen[key] = seen.get(key, 0) + 1
        return {**item, "gate": gate}

    by_source: dict[str, list] = {}
    for item in pool:
        by_source.setdefault(item["source"], []).append(item)

    chosen, depth = [], 0
    deepest = max((len(v) for v in by_source.values()), default=0)
    while len(chosen) < per_cell and depth < deepest:
        for source in sorted(by_source):
            if len(chosen) >= per_cell:
                break
            if depth < len(by_source[source]):
                picked = take(by_source[source][depth], "passed")
                if picked:
                    chosen.append(picked)
        depth += 1

    for row in rng.sample(refused, len(refused)):
        if sum(1 for c in chosen if c["gate"] == "refused") >= refused_per_cell:
            break
        picked = take({"signal_id": row.get("signal_id"), "source": row.get("source"),
                       "text": row.get("text"), "context": None, "is_national": False,
                       "refuse_reason": row.get("reason")}, "refused")
        if picked:
            chosen.append(picked)

    rng.shuffle(chosen)                              # defeat position anchoring
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parquet", type=Path, required=True,
                        help="clean/signal_candidate.parquet")
    parser.add_argument("--brands", type=Path, required=True,
                        help="brandvoice_briefs.parquet")
    parser.add_argument("--out-dir", type=Path, default=Path("training/out/review-01"))
    parser.add_argument("--cells", type=int, default=30,
                        help="brand x state x brief combinations (default 30)")
    parser.add_argument("--candidates-per-cell", type=int, default=8)
    parser.add_argument("--refused-per-cell", type=int, default=2,
                        help="safety-gate refusals to include, for its false-positive rate")
    parser.add_argument("--overlap", type=int, default=50,
                        help="rows copied out for a second reviewer")
    parser.add_argument("--states", nargs="*", default=DEFAULT_STATES)
    parser.add_argument("--briefs-file", type=Path,
                        help="JSON array of briefs; defaults to a built-in set")
    parser.add_argument("--max-brands", type=int, default=12)
    parser.add_argument("--max-repeats", type=int, default=1,
                        help="times one distinct signal may appear across the whole set")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-rank", action="store_true",
                        help="skip the LLM ranker; review stage 1 only (no API calls)")
    parser.add_argument("--as-of", help="YYYY-MM-DD treated as today, for a fixed snapshot")
    args = parser.parse_args()

    # src/backend/db.py connects to Mongo and builds indexes at import time.
    # This builder reads the parquet directly, so stand in for that module
    # before importing the services -- the pool logic itself is unchanged.
    collection = ParquetCollection(load_candidates(args.parquet))
    stub = types.ModuleType("db")
    for name in ("users_collection", "feedback_collection", "history_collection",
                 "state_signals_collection", "projects_collection", "db", "client"):
        setattr(stub, name, None)
    stub.signal_candidates_collection = collection
    sys.modules.setdefault("db", stub)

    from services import candidate_service
    from services import ranker_service

    candidate_service.signal_candidates_collection = collection

    briefs = (json.loads(args.briefs_file.read_text()) if args.briefs_file
              else DEFAULT_BRIEFS)
    brands = load_brands(args.brands, args.max_brands)
    if not brands:
        raise SystemExit("No brands loaded -- check --brands.")

    today = date.fromisoformat(args.as_of) if args.as_of else None
    rng = random.Random(args.seed)

    grid = [(b, s, f) for b in brands for s in args.states for f in briefs]
    rng.shuffle(grid)

    review_rows, model_rows = [], []
    skipped = []
    seen: dict[str, int] = {}
    row_id = 0

    for cell_index, (brand, state, brief) in enumerate(grid):
        if len({r["sample_id"] for r in review_rows}) >= args.cells:
            break
        bundle = candidate_service.get_candidate_pool(state, today=today)
        if not bundle["pool"]:
            skipped.append({"state": state, "reason": "empty pool"})
            continue

        sample_id = f"s{cell_index:04d}"
        scores: dict[str, dict] = {}
        method = "not-ranked"
        if not args.no_rank:
            audit: dict = {}
            _, method = ranker_service.rank_signals(brief, brand, state,
                                                    bundle["pool"], audit=audit)
            ranked = sorted(
                [a for a in audit.get("assessments", []) if a.get("score") is not None],
                key=lambda a: a["score"], reverse=True)
            rank_of = {a["signal_id"]: i + 1 for i, a in enumerate(ranked)}
            scores = {a["signal_id"]: {"score": a.get("score"),
                                       "why": a.get("why"),
                                       "status": a.get("assessment_status"),
                                       "model_rank": rank_of.get(a["signal_id"])}
                      for a in audit.get("assessments", [])}

        picked = pick_candidates(bundle["pool"], bundle["refused"],
                                 args.candidates_per_cell, args.refused_per_cell,
                                 rng, seen=seen, max_repeats=args.max_repeats)
        if not picked:
            skipped.append({"state": state, "reason": "no unseen candidates"})
            continue
        for item in picked:
            row_id += 1
            rid = f"r{row_id:05d}"
            review_rows.append({
                "row_id": rid, "sample_id": sample_id, "state": state,
                "brand": brand["name"], "industry": brand["industry"] or "",
                "brief": brief, "source": item["source"],
                "geo": "national" if item.get("is_national") else "state",
                "gate": item.get("gate", "passed"),
                "signal_text": item.get("text") or "",
                "signal_context": item.get("context") or "",
                "usable": "", "would_use_first": "", "notes": "", "reviewer": "",
            })
            model_rows.append({
                "row_id": rid, "sample_id": sample_id, "state": state,
                "brand": brand["name"], "brief": brief,
                "signal_id": item.get("signal_id"), "source": item["source"],
                "gate": item.get("gate", "passed"),
                "refuse_reason": item.get("refuse_reason"),
                "rank_method": method,
                "as_of": bundle["as_of"], "stale_days": bundle["stale_days"],
                "pool_size": len(bundle["pool"]),
                **(scores.get(item.get("signal_id"), {}) if item.get("gate") != "refused" else {}),
            })

    if not review_rows:
        raise SystemExit("No rows produced -- is the snapshot date outside the "
                         "freshness window? Try --as-of with the snapshot's date.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.out_dir / "review.csv"
    with open(review_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review_rows)

    with open(args.out_dir / "model.jsonl", "w", encoding="utf-8") as handle:
        for row in model_rows:
            handle.write(json.dumps(row, default=str) + "\n")

    overlap = rng.sample(review_rows, min(args.overlap, len(review_rows)))
    with open(args.out_dir / "overlap.csv", "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(overlap)

    (args.out_dir / "README.txt").write_text(
        f"""Retrieval review set
seed={args.seed}  cells={len({r['sample_id'] for r in review_rows})}  rows={len(review_rows)}
ranker={'skipped' if args.no_rank else 'run'}

Label review.csv. One row = one candidate signal shown for one brand/state/brief.

  usable           {USABLE_GUIDE}
  would_use_first  y on exactly ONE row per sample_id -- the single best hook.
                   Leave every row blank for that sample if none are worth using.
  notes            free text, especially for anything you scored 0
  reviewer         your name, on every row you label

Do not open model.jsonl before labelling: it holds the model's scores and
would anchor your judgement. overlap.csv is the same rows for a second
reviewer; label it independently, do not compare first.

Then: python training/score_retrieval_review.py {args.out_dir}
""")

    print(f"wrote {len(review_rows)} rows across "
          f"{len({r['sample_id'] for r in review_rows})} samples -> {review_path}")
    print(f"      {len(overlap)} rows for a second reviewer -> {args.out_dir / 'overlap.csv'}")
    if skipped:
        print(f"      skipped {len(skipped)} cells with an empty pool "
              f"({', '.join(sorted({s['state'] for s in skipped}))})")
    gates = sum(1 for r in review_rows if r["gate"] == "refused")
    distinct = len({normalise(r["signal_text"]) for r in review_rows})
    national = sum(1 for r in review_rows if r["geo"] == "national")
    print(f"      {gates} rows are safety-gate refusals")
    print(f"      {distinct} distinct signals ({national} national rows)")
    if distinct < len(review_rows) * 0.9:
        print("      warning: repeats are eating the review budget; "
              "check --max-repeats")


if __name__ == "__main__":
    main()
"""
Turns a labelled retrieval review set into the numbers for the session report.

    python training/score_retrieval_review.py training/out/review-01

Reads review.csv (labelled by hand) and model.jsonl (the withheld model
scores), joins them on row_id, and reports:

  precision@3        of the signals the ranker would have used, how many a
                     human would also use. This is the headline number.
  recall of usable   of the signals a human marked usable, how many the
                     ranker put in its top 3. Catches good hooks it ignored.
  top-1 agreement    does the ranker's best pick match the human's.
  per source         where the ranker is strong and where it is guessing.
  gate precision     of the signals the safety gate refused, how many a human
                     also calls unusable. Low means the gate is over-eager.
  Cohen's kappa      two reviewers on the overlap slice. Without this the
                     numbers above have no ceiling to be read against.

Every figure is printed with its denominator, because on 300 rows most of
them rest on fewer samples than they look like they do.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

TOP_K = 3
USABLE_THRESHOLD = 2          # only "would use" counts as a positive


def read_review(path: Path) -> list[dict]:
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    labelled = [r for r in rows if (r.get("usable") or "").strip() != ""]
    for row in labelled:
        try:
            row["usable_score"] = int(row["usable"])
        except ValueError:
            raise SystemExit(f"{path.name} row {row['row_id']}: "
                             f"usable must be 0, 1 or 2 (got {row['usable']!r})")
        if row["usable_score"] not in (0, 1, 2):
            raise SystemExit(f"{path.name} row {row['row_id']}: "
                             f"usable must be 0, 1 or 2 (got {row['usable']})")
    return rows, labelled


def read_model(path: Path) -> dict[str, dict]:
    with open(path) as handle:
        return {json.loads(line)["row_id"]: json.loads(line) for line in handle if line.strip()}


def pct(numerator: int, denominator: int) -> str:
    if not denominator:
        return "  n/a (0)"
    return f"{100 * numerator / denominator:5.1f}%  ({numerator}/{denominator})"


def cohens_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Two raters, three ordered categories, treated nominally (conservative)."""
    if not pairs:
        return None
    categories = sorted({v for pair in pairs for v in pair})
    total = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / total
    expected = sum(
        (sum(1 for a, _ in pairs if a == c) / total) * (sum(1 for _, b in pairs if b == c) / total)
        for c in categories)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("review_dir", type=Path)
    args = parser.parse_args()

    all_rows, rows = read_review(args.review_dir / "review.csv")
    model = read_model(args.review_dir / "model.jsonl")
    if not rows:
        raise SystemExit("No labelled rows yet -- fill in the `usable` column first.")

    print(f"labelled {len(rows)} of {len(all_rows)} rows "
          f"({len({r['sample_id'] for r in rows})} samples, "
          f"{len({r['reviewer'] for r in rows if r['reviewer']})} reviewers)\n")

    passed = [r for r in rows if r["gate"] == "passed"]
    refused = [r for r in rows if r["gate"] == "refused"]

    # ---- staleness, reported first because it invalidates everything else ----
    stale = {m.get("stale_days") for m in model.values() if m.get("stale_days") is not None}
    methods = {m.get("rank_method") for m in model.values()}
    print(f"snapshot staleness (days): {sorted(stale) if stale else 'unknown'}")
    print(f"rank method(s): {', '.join(sorted(m for m in methods if m))}\n")

    # ---- precision / recall of the ranker's top 3 ----
    in_top_k, human_positive = [], []
    for row in passed:
        entry = model.get(row["row_id"], {})
        rank = entry.get("model_rank")
        picked = rank is not None and rank <= TOP_K
        positive = row["usable_score"] >= USABLE_THRESHOLD
        in_top_k.append((row, picked, positive))
        if positive:
            human_positive.append(row)

    picked_rows = [(r, p) for r, picked, p in in_top_k if picked]
    print("RANKER")
    print("  precision@3        ",
          pct(sum(1 for _, positive in picked_rows if positive), len(picked_rows)))
    print("  recall of usable   ",
          pct(sum(1 for row, picked, positive in in_top_k if picked and positive),
              len(human_positive)))
    print("  lenient precision@3 (counts 'plausible stretch' too)",
          pct(sum(1 for row, picked, _ in in_top_k
                  if picked and row["usable_score"] >= 1), len(picked_rows)))

    # ---- top-1 agreement, per sample ----
    agree = total = 0
    for sample_id in sorted({r["sample_id"] for r in passed}):
        sample = [r for r in passed if r["sample_id"] == sample_id]
        human_first = [r for r in sample
                       if (r.get("would_use_first") or "").strip().lower().startswith("y")]
        ranked = [(model.get(r["row_id"], {}).get("model_rank"), r) for r in sample]
        ranked = sorted([(rank, r) for rank, r in ranked if rank], key=lambda x: x[0])
        if not human_first or not ranked:
            continue
        total += 1
        agree += ranked[0][1]["row_id"] == human_first[0]["row_id"]
    print("  top-1 agreement    ", pct(agree, total))

    # ---- per source ----
    print("\nPER SOURCE (human 'would use' rate, and share the ranker put in top 3)")
    by_source = defaultdict(list)
    for row, picked, positive in in_top_k:
        by_source[row["source"]].append((picked, positive))
    for source in sorted(by_source):
        items = by_source[source]
        print(f"  {source:10} usable {pct(sum(1 for _, p in items if p), len(items))}"
              f"   picked {pct(sum(1 for k, _ in items if k), len(items))}")

    # ---- the safety gate ----
    print("\nSAFETY GATE")
    if refused:
        correct = sum(1 for r in refused if r["usable_score"] == 0)
        print("  refusals a human also rejects", pct(correct, len(refused)))
        wrong = [r for r in refused if r["usable_score"] >= USABLE_THRESHOLD]
        if wrong:
            print(f"  over-eager refusals ({len(wrong)}) -- tune these terms:")
            for row in wrong[:8]:
                reason = model.get(row["row_id"], {}).get("refuse_reason", "?")
                print(f"    [{reason}] {row['signal_text'][:58]}")
    else:
        print("  no refused rows were labelled")

    # ---- agreement ----
    overlap_path = args.review_dir / "overlap.csv"
    print("\nAGREEMENT")
    if overlap_path.exists():
        _, second = read_review(overlap_path)
        first_by_id = {r["row_id"]: r["usable_score"] for r in rows}
        pairs = [(first_by_id[r["row_id"]], r["usable_score"])
                 for r in second if r["row_id"] in first_by_id]
        kappa = cohens_kappa(pairs)
        if kappa is None:
            print("  not enough overlapping labels yet")
        else:
            raw = sum(1 for a, b in pairs if a == b) / len(pairs)
            print(f"  Cohen's kappa {kappa:.2f} on {len(pairs)} shared rows "
                  f"(raw agreement {100 * raw:.0f}%)")
            if kappa < 0.4:
                print("  below 0.4: reviewers are not applying the same standard. "
                      "Fix the guidance before trusting the numbers above.")
    else:
        print("  overlap.csv not labelled -- no ceiling for the numbers above")

    print("\nReport precision@3 and recall together. Precision alone is gameable "
          "by selecting nothing;\nrecall alone is gameable by selecting everything.")


if __name__ == "__main__":
    main()
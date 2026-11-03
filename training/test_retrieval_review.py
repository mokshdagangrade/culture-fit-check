import csv
import importlib.util
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load(name):
    """Load a training script by path; they are scripts, not an installed package."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "training" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


make = load("make_retrieval_review")
score = load("score_retrieval_review")


def row(state="TX", source="trends", text="a signal", national=False,
        dup=False, noise=False, in_window=True, day="2026-10-20"):
    return {"signal_id": f"{state}|{day}|{source}|{text}", "state_code": state,
            "date": day, "source": source, "position": 1, "text": text,
            "context": None, "is_national": national, "is_dup": dup,
            "is_noise": noise, "is_within_window": in_window}


class ParquetCollectionTests(unittest.TestCase):
    def query(self, rows, state="TX"):
        collection = make.ParquetCollection(rows)
        return collection.find({
            "date": {"$gte": "2026-10-18", "$lte": "2026-10-20"},
            "$or": [{"state_code": state}, {"is_national": True}],
            "is_dup": False, "is_noise": False, "is_within_window": True,
        }, {"_id": 0}).sort([("date", -1), ("position", 1)])

    def test_keeps_the_state_and_national_rows_only(self):
        rows = [row(state="TX"), row(state="CA"), row(state=None, national=True)]
        kept = self.query(rows)
        self.assertEqual({r["state_code"] for r in kept}, {"TX", None})

    def test_drops_duplicates_noise_and_out_of_window(self):
        rows = [row(text="keep"), row(text="dup", dup=True),
                row(text="noisy", noise=True), row(text="stale", in_window=False)]
        self.assertEqual([r["text"] for r in self.query(rows)], ["keep"])

    def test_respects_the_date_range(self):
        rows = [row(text="recent"), row(text="ancient", day="2026-09-01")]
        self.assertEqual([r["text"] for r in self.query(rows)], ["recent"])


class CandidatePickingTests(unittest.TestCase):
    def test_spreads_across_sources_rather_than_taking_one(self):
        pool = ([{"source": "events", "text": f"e{i}", "signal_id": f"e{i}"} for i in range(20)]
                + [{"source": "trends", "text": f"t{i}", "signal_id": f"t{i}"} for i in range(5)])
        picked = make.pick_candidates(pool, [], 8, 0, random.Random(1))
        self.assertEqual(len(picked), 8)
        self.assertIn("trends", {p["source"] for p in picked})
        self.assertLessEqual(sum(1 for p in picked if p["source"] == "events"), 5)

    def test_refused_rows_are_included_and_marked(self):
        pool = [{"source": "trends", "text": "ok", "signal_id": "a"}]
        refused = [{"signal_id": "b", "source": "news", "text": "shooting",
                    "reason": "violence:shooting"}]
        picked = make.pick_candidates(pool, refused, 1, 1, random.Random(1))
        gates = {p["gate"] for p in picked}
        self.assertEqual(gates, {"passed", "refused"})
        self.assertEqual([p["refuse_reason"] for p in picked if p["gate"] == "refused"],
                         ["violence:shooting"])

    def test_order_is_shuffled_so_the_reviewer_cannot_anchor(self):
        pool = [{"source": "trends", "text": f"t{i}", "signal_id": f"t{i}"} for i in range(12)]
        a = [p["text"] for p in make.pick_candidates(pool, [], 12, 0, random.Random(1))]
        b = [p["text"] for p in make.pick_candidates(pool, [], 12, 0, random.Random(2))]
        self.assertNotEqual(a, b)

    def test_review_columns_never_carry_a_model_score(self):
        for field in make.REVIEW_FIELDS:
            self.assertNotIn("score", field)
            self.assertNotIn("rank", field)


class ScoringTests(unittest.TestCase):
    def write(self, directory, labels, ranks, overlap=None):
        path = Path(directory)
        fields = make.REVIEW_FIELDS
        rows = []
        for i, (usable, first, source, gate) in enumerate(labels, 1):
            rows.append({**{f: "" for f in fields},
                         "row_id": f"r{i}", "sample_id": "s1", "source": source,
                         "gate": gate, "signal_text": f"signal {i}",
                         "usable": usable, "would_use_first": first,
                         "reviewer": "tester"})
        with open(path / "review.csv", "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with open(path / "model.jsonl", "w") as handle:
            for i, rank in enumerate(ranks, 1):
                handle.write(json.dumps({"row_id": f"r{i}", "sample_id": "s1",
                                         "gate": rows[i - 1]["gate"],
                                         "model_rank": rank, "stale_days": 0,
                                         "rank_method": "llm",
                                         "refuse_reason": "death:dead"}) + "\n")
        if overlap is not None:
            with open(path / "overlap.csv", "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for i, usable in enumerate(overlap, 1):
                    writer.writerow({**{f: "" for f in fields}, "row_id": f"r{i}",
                                     "sample_id": "s1", "gate": rows[i - 1]["gate"],
                                     "usable": usable, "reviewer": "second"})
        return path

    def test_rejects_an_out_of_range_label(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, [("5", "", "trends", "passed")], [1])
            with self.assertRaises(SystemExit):
                score.read_review(path / "review.csv")

    def test_blank_labels_are_treated_as_unlabelled_not_as_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, [("2", "y", "trends", "passed"),
                                          ("", "", "news", "passed")], [1, 2])
            _, labelled = score.read_review(path / "review.csv")
            self.assertEqual(len(labelled), 1)

    def test_kappa_is_one_on_perfect_agreement_and_low_on_disagreement(self):
        self.assertAlmostEqual(score.cohens_kappa([(0, 0), (2, 2), (1, 1), (0, 0)]), 1.0)
        self.assertLess(score.cohens_kappa([(0, 2), (2, 0), (1, 0), (0, 1)]), 0.3)
        self.assertIsNone(score.cohens_kappa([]))

    def test_kappa_is_none_when_everyone_used_one_category(self):
        self.assertIsNone(score.cohens_kappa([(2, 2), (2, 2)]))


if __name__ == "__main__":
    unittest.main()
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

database = MagicMock()
with patch.dict(sys.modules, {"db": database}):
    from services import candidate_service

from prompt_builder import build_context_prompt, format_signals
from services.ranker_service import SCORE_FLOOR, build_ranking_prompt, parse_ranking


def rows(*specs):
    out = []
    for i, (source, text) in enumerate(specs):
        out.append({"signal_id": f"s{i}", "state_code": "TX", "date": "2026-10-20",
                    "source": source, "position": i, "text": text, "context": None,
                    "is_national": False, "is_dup": False, "is_noise": False,
                    "is_within_window": True})
    return out


class CandidatePoolTests(unittest.TestCase):
    def pool_for(self, docs, state="Texas", today=date(2026, 10, 20)):
        cursor = MagicMock()
        cursor.sort.return_value = docs
        database.signal_candidates_collection.find.return_value = cursor
        with patch.object(candidate_service, "signal_candidates_collection",
                          database.signal_candidates_collection):
            return candidate_service.get_candidate_pool(state, today=today)

    def test_quota_stops_events_swallowing_the_pool(self):
        # the real Texas day was 1,000 events out of 1,315 candidates
        docs = rows(*[("events", f"concert {i}") for i in range(200)],
                    *[("trends", f"trend {i}") for i in range(5)])
        result = self.pool_for(docs)
        counts = result["counts"]
        self.assertLessEqual(counts["events"], candidate_service.SOURCE_QUOTA["events"])
        self.assertEqual(counts["trends"], 5, "trends must survive the event flood")

    def test_pool_is_capped_and_mixes_sources(self):
        docs = rows(*[("events", f"e{i}") for i in range(50)],
                    *[("news", f"n{i}") for i in range(50)],
                    *[("social", f"s{i}") for i in range(50)])
        result = self.pool_for(docs)
        self.assertLessEqual(len(result["pool"]), candidate_service.POOL_SIZE)
        self.assertEqual({p["source"] for p in result["pool"]}, {"events", "news", "social"})

    def test_unsafe_candidates_are_refused_with_a_reason(self):
        docs = rows(("news", "downtown shooting"), ("trends", "pumpkin spice latte"))
        result = self.pool_for(docs)
        self.assertEqual([p["text"] for p in result["pool"]], ["pumpkin spice latte"])
        self.assertEqual(result["refused"][0]["reason"], "violence:shooting")

    def test_reports_staleness_rather_than_hiding_it(self):
        docs = rows(("trends", "first frost austin"))
        result = self.pool_for(docs, today=date(2026, 10, 21))
        self.assertEqual(result["as_of"], "2026-10-20")
        self.assertEqual(result["stale_days"], 1)

    def test_unknown_state_and_empty_db_are_survivable(self):
        self.assertEqual(self.pool_for([], state="Maharashtra")["pool"], [])
        self.assertEqual(self.pool_for([])["pool"], [])


class RankerTests(unittest.TestCase):
    pool = [{"source": "trends", "text": "first frost austin", "context": None},
            {"source": "events", "text": "Monster Jam", "context": "Alamodome"}]

    def test_prompt_numbers_candidates_and_demands_json(self):
        prompt = build_ranking_prompt("Launch autumn blend", {"name": "Joe's"}, "Texas", self.pool)
        self.assertIn("0. (trends) first frost austin", prompt)
        self.assertIn("1. (events) Monster Jam -- Alamodome", prompt)
        self.assertIn("JSON only", prompt)

    def test_parses_scores_and_drops_weak_ones(self):
        raw = '[{"id":0,"score":9,"why":"seasonal fit"},{"id":1,"score":2,"why":"no link"}]'
        selected = parse_ranking(raw, self.pool)
        self.assertEqual([s["text"] for s in selected], ["first frost austin"])
        self.assertEqual(selected[0]["why"], "seasonal fit")

    def test_tolerates_code_fences_and_surrounding_prose(self):
        raw = 'Here you go:\n```json\n[{"id": 0, "score": 8, "why": "fits"}]\n```\nHope that helps!'
        self.assertEqual(len(parse_ranking(raw, self.pool)), 1)

    def test_out_of_range_ids_cannot_inject_a_signal(self):
        self.assertEqual(parse_ranking('[{"id":99,"score":10},{"id":-1,"score":10}]', self.pool), [])

    def test_empty_selection_is_a_valid_answer(self):
        self.assertEqual(parse_ranking("[]", self.pool), [])

    def test_unparseable_reply_raises_for_the_caller_to_fall_back(self):
        with self.assertRaises(ValueError):
            parse_ranking("I could not decide.", self.pool)

    def test_score_floor_is_enforced(self):
        raw = f'[{{"id":0,"score":{SCORE_FLOOR - 1}}}]'
        self.assertEqual(parse_ranking(raw, self.pool), [])


class SignalRenderingTests(unittest.TestCase):
    def test_renders_source_context_and_reason(self):
        out = format_signals([{"source": "trends", "text": "first frost austin",
                               "context": "cold snap", "why": "seasonal fit"}])
        self.assertIn("1. (trends) first frost austin", out)
        self.assertIn("context: cold snap", out)
        self.assertIn("why it may fit: seasonal fit", out)

    def test_national_signals_are_labelled_as_not_local(self):
        out = format_signals([{"source": "youtube", "text": "a video", "is_national": True}])
        self.assertIn("[national, not local]", out)

    def test_signals_replace_the_trends_section_when_present(self):
        _, brief = build_context_prompt(
            "Launch autumn blend", location={"state": "Texas", "country": "US"},
            trends=[{"keyword": "should not appear"}],
            signals=[{"source": "trends", "text": "first frost austin"}],
            trends_as_of="2026-10-20")
        self.assertIn("## LOCAL SIGNALS -- Texas, US, 2026-10-20", brief)
        self.assertIn("first frost austin", brief)
        self.assertNotIn("should not appear", brief)

    def test_falls_back_to_the_trends_section_with_no_signals(self):
        _, brief = build_context_prompt(
            "Launch autumn blend", location={"state": "Texas", "country": "US"},
            trends=[{"keyword": "first frost austin", "rank": 2}])
        self.assertIn("## LOCAL TREND SIGNALS -- Texas, US", brief)
        self.assertIn("first frost austin", brief)

    def test_no_stray_empty_heading(self):
        _, brief = build_context_prompt("x", location={"state": "Texas"})
        self.assertNotIn("## CURRENT TRENDS", brief)


if __name__ == "__main__":
    unittest.main()
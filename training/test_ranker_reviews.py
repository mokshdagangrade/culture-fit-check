"""Offline checks for score preservation, selection, and review export."""
import importlib.util
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from export_ranker_reviews import review_rows

# Load just the ranker: no backend DB imports, API keys, or installed SDK needed.
spec = importlib.util.spec_from_file_location(
    "review_test_ranker", Path(__file__).resolve().parents[1] / "src/backend/services/ranker_service.py")
ranker = importlib.util.module_from_spec(spec)
fake_llm = MagicMock()
fake_llm.LLMError = RuntimeError
with patch.dict(sys.modules, {"llm": fake_llm}):
    spec.loader.exec_module(ranker)


class RankerReviewTests(unittest.TestCase):
    def setUp(self):
        fake_llm.reset_mock()
        fake_llm.is_configured.return_value = True
        self.pool = [{"signal_id": f"s{i}", "source": "social", "text": f"signal {i}",
                      "geo_confidence": "guessed"} for i in range(6)]

    def test_all_scores_survive_but_only_three_reach_generation(self):
        fake_llm.call_llm.return_value = json.dumps([
            {"id": i, "score": score, "why": "fit"} for i, score in enumerate([0, 2, 5, 7, 9, 10])])
        audit = {}
        selected, method = ranker.rank_signals("Launch", {"products": "Coffee"}, "Texas", self.pool, audit)
        self.assertEqual(method, "llm")
        self.assertEqual([s["score"] for s in selected], [10, 9, 7])
        self.assertEqual([s["score"] for s in audit["assessments"]], [0, 2, 5, 7, 9, 10])
        self.assertEqual(audit["company"]["products"], "Coffee")
        self.assertTrue(all(s["geo_confidence"] == "guessed" for s in audit["assessments"]))

    def test_missing_invalid_scores_stay_unknown_and_first_valid_duplicate_wins(self):
        raw = '[{"id":0,"score":0},{"id":1,"score":true},{"id":2.9,"score":8},' \
              '{"id":3,"score":NaN},{"id":4,"score":7},{"id":4,"score":8}]'
        rows = ranker.parse_assessments(raw, self.pool)
        self.assertEqual(rows[0]["score"], 0)
        self.assertTrue(all(rows[i]["score"] is None for i in (1, 2, 3, 5)))
        self.assertEqual(rows[4]["score"], 7)
        self.assertEqual([r["score"] for r in ranker.select_assessments(rows)], [7])

    def test_generation_output_shape_and_numeric_strings_remain_compatible(self):
        selected = ranker.parse_ranking('[{"id":"0","score":"8","why":"fits"}]', self.pool)
        self.assertEqual(selected, [{**self.pool[0], "score": 8.0, "why": "fits"}])
        self.assertEqual(ranker.parse_ranking('[{"id":0.9,"score":8}]', self.pool), [])

    def test_empty_pool_and_missing_provider_keep_existing_fallbacks(self):
        self.assertEqual(ranker.rank_signals("Launch", {}, "Texas", []), ([], "empty-pool"))
        fake_llm.is_configured.return_value = False
        audit = {}
        self.assertEqual(ranker.rank_signals("Launch", {}, "Texas", self.pool, audit),
                         ([], "fallback:no-llm"))
        fake_llm.call_llm.assert_not_called()
        self.assertTrue(all(r["score"] is None for r in audit["assessments"]))

    def test_failure_keeps_candidates_unassessed(self):
        for reply in ("[]", "broken JSON"):
            fake_llm.call_llm.return_value = reply
            audit = {}
            selected, _ = ranker.rank_signals("Launch", {}, "Texas", self.pool, audit)
            self.assertEqual(selected, [])
            self.assertTrue(all(row["score"] is None for row in audit["assessments"]))
        fake_llm.call_llm.side_effect = RuntimeError("provider unavailable")
        try:
            audit = {}
            self.assertEqual(ranker.rank_signals("Launch", {}, "Texas", self.pool, audit)[1], "fallback:llm-error")
            self.assertEqual(len(audit["assessments"]), 6)
        finally:
            fake_llm.call_llm.side_effect = None

    def test_prompt_includes_company_context(self):
        prompt = ranker.build_ranking_prompt("Launch", {"description": "Roaster",
                    "products": "Coffee", "target_audience": "Commuters"}, "Texas", self.pool)
        for value in ("Roaster", "Coffee", "Commuters", "EVERY candidate", "guessed geography"):
            self.assertIn(value, prompt)

    def test_score_boundaries_ties_and_input_immutability(self):
        original = copy.deepcopy(self.pool)
        rows = ranker.parse_assessments(json.dumps([
            {"id": i, "score": score} for i, score in enumerate([0, 4.99, 5, 10, 10, 10.01])]), self.pool)
        self.assertEqual([r["signal_id"] for r in ranker.select_assessments(rows)], ['s3', 's4', 's2'])
        self.assertEqual(rows[0]['score'], 0)
        self.assertIsNone(rows[5]['score'])
        self.assertEqual(self.pool, original)

    def test_malformed_rows_do_not_hide_a_valid_judgment(self):
        invalid = [None, [], 'text', {}, {'id': True, 'score': 9},
                   {'id': -1, 'score': 9}, {'id': 999, 'score': 9},
                   {'id': 0, 'score': None}, {'id': 0, 'score': []},
                   {'id': 0, 'score': 'Infinity'}, {'id': 0, 'score': '-Infinity'},
                   {'id': 0, 'score': 10 ** 400}, {'id': 1, 'score': 8}]
        rows = ranker.parse_assessments(json.dumps(invalid), self.pool)
        self.assertIsNone(rows[0]['score'])
        self.assertEqual([r['signal_id'] for r in ranker.select_assessments(rows)], ['s1'])

    def test_truncated_and_wrong_shape_replies_abstain(self):
        for reply in ('[{"id":0,"score":9}', '{}', 'null', '"text"'):
            with self.subTest(reply=reply):
                fake_llm.call_llm.return_value = reply
                audit = {}
                self.assertEqual(ranker.rank_signals('Launch', {}, 'Texas', self.pool, audit),
                                 ([], 'fallback:bad-json'))
                self.assertTrue(all(r['score'] is None for r in audit['assessments']))

    def test_full_pool_is_scored_once_without_changing_selection_limit(self):
        pool = [{**self.pool[0], 'signal_id': f's{i}'} for i in range(40)]
        fake_llm.call_llm.return_value = json.dumps([{'id': i, 'score': i % 11} for i in range(40)])
        audit = {}
        selected, _ = ranker.rank_signals('Launch', {}, 'Texas', pool, audit)
        fake_llm.call_llm.assert_called_once()
        self.assertEqual(len(audit['assessments']), 40)
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(r['score'] == 10 for r in selected))

    def test_audits_do_not_mix_between_requests(self):
        fake_llm.call_llm.return_value = '[{"id":0,"score":9}]'
        first, second = {}, {}
        ranker.rank_signals('Coffee', {'name': 'A'}, 'Texas', self.pool, first)
        before = copy.deepcopy(first)
        fake_llm.is_configured.return_value = False
        ranker.rank_signals('Shoes', {'name': 'B'}, 'California', self.pool, second)
        self.assertEqual(first, before)
        self.assertEqual(second['brief'], 'Shoes')
        self.assertTrue(all(r['score'] is None for r in second['assessments']))

    def test_export_preserves_scores_and_leaves_human_fields_blank(self):
        audit = {"brief": "Coffee launch", "state": "Texas", "company": {"products": "Coffee"},
                 "assessments": ranker.parse_assessments('[{"id":0,"score":0}]', self.pool)}
        selection = {"ranking_audit": audit, "selected": [], "method": "llm"}
        entries = [{"id": "h1", "results": [{"grounding_context": {"signal_selection": selection}}]}]
        rows = list(review_rows(entries))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["model_score"], 0)
        self.assertIsNone(rows[1]["model_score"])
        self.assertEqual(rows[1]["assessment_status"], "unassessed")
        self.assertTrue(all(r["human_relevance"] is None and r["human_suitability"] is None for r in rows))

    def test_legacy_omissions_are_not_negative_labels(self):
        selection = {"pool": self.pool, "selected": [{**self.pool[0], "score": 9}], "method": "llm"}
        rows = list(review_rows([{"results": [{"grounding_context": {"signal_selection": selection}}]}]))
        self.assertTrue(rows[0]["selected_for_generation"])
        self.assertEqual(rows[0]["model_score"], 9)
        self.assertIsNone(rows[1]["model_score"])
        self.assertIsNone(rows[0]["company"])

    def test_chat_empty_and_null_grounding_have_no_candidate_pairs(self):
        self.assertEqual(list(review_rows([{'response': 'Hello'}, {'results': None},
            {'results': [{'grounding_context': None}, {'grounding_context': {'signal_selection': None}}]}])), [])

    def test_export_keeps_same_signal_separate_for_different_briefs_and_states(self):
        entries = [{'id': f'h{i}', 'prompt': brief, 'results': [{'state': state,
            'grounding_context': {'signal_selection': {'pool': [self.pool[0]], 'selected': []}}}]}
            for i, (brief, state) in enumerate([('Coffee', 'Texas'), ('Shoes', 'California')])]
        rows = list(review_rows(entries))
        self.assertEqual([(r['brief'], r['state']) for r in rows], [('Coffee', 'Texas'), ('Shoes', 'California')])
        self.assertTrue(all(r['model_score'] is None for r in rows))

    def test_bad_export_input_does_not_create_a_partial_file(self):
        valid = {'results': [{'grounding_context': {'signal_selection': {'pool': self.pool}}}]}
        for data in ({'entries': 'invalid'}, [valid, {'results': [42]}]):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory) / 'history.json', Path(directory) / 'reviews.jsonl'
                source.write_text(json.dumps(data))
                result = subprocess.run([sys.executable, str(Path(__file__).with_name('export_ranker_reviews.py')),
                    str(source), '--output', str(output)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_cli_exports_history_and_protects_existing_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.json"
            output = Path(directory) / "reviews.jsonl"
            source.write_text(json.dumps({"entries": [{"prompt": "Launch",
                "results": [{"state": "Texas", "grounding_context": {
                    "signal_selection": {"pool": self.pool, "selected": []}}}]}]}))
            command = [sys.executable, str(Path(__file__).with_name("export_ranker_reviews.py")),
                       str(source), "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_text()
            rows = [json.loads(line) for line in original.splitlines()]
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row["model_score"] is None for row in rows))
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_text(), original)


if __name__ == "__main__":
    unittest.main()

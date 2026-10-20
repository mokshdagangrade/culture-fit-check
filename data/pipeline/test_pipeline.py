"""Focused offline checks for age settings, calendar requests and state stitching."""

import ast
import json
import os
import re
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from extractors.calendar import fetch_calendar_batch, holiday_locations
from extractors.events import fetch_events
from signal_windows import SignalWindow, load_windows
from validate import check_batch
from stitch import stitch_state
from extractors.weather import fetch_weather
from extractors.social import fetch_subreddit_posts
from us_states import US_STATES
from schemas import ErrorDoc, EventItem, EventsDoc, SourceMeta, GeoTag

PIPELINE = Path(__file__).resolve().parent


class WindowTests(unittest.TestCase):
    def test_window_validation_and_year_bounds(self):
        start, end = SignalWindow(21, 30).bounds(date(2026, 12, 20))
        self.assertEqual((start, end), (date(2026, 11, 29), date(2027, 1, 19)))
        for values in [(-1, 0), (True, 0), (1.5, 0)]:
            with self.assertRaises(ValueError):
                SignalWindow(*values)

    def test_custom_windows_and_unknown_source(self):
        settings = json.loads((PIPELINE / "signal_windows.json").read_text())
        settings["events"] = {"lookback_days": 5, "lookahead_days": 60}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "windows.json"
            path.write_text(json.dumps(settings))
            self.assertEqual(load_windows(path)["events"], SignalWindow(5, 60))
            settings["newss"] = settings.pop("news")
            path.write_text(json.dumps(settings))
            with self.assertRaises(ValueError):
                load_windows(path)


class CalendarTests(unittest.TestCase):
    def test_location_mapping(self):
        self.assertEqual(holiday_locations({"locations": "All"}), (True, []))
        self.assertEqual(holiday_locations({"states": [{"iso": "us-al"}, {"abbrev": "AK"}]}), (False, ["AK", "AL"]))
        self.assertEqual(holiday_locations({"locations": "Alabama, Alaska"}), (False, ["AK", "AL"]))
        self.assertEqual(holiday_locations({"locations": "US-PR"}), (False, []))
        for raw in [{}, {"locations": "somewhere"}, {"states": [{}]}]:
            with self.assertRaises(ValueError):
                holiday_locations(raw)

    @patch.dict(os.environ, {"CALENDARIFIC_API_KEY": "test-key"})
    @patch("extractors.calendar.polite_get")
    def test_one_request_for_50_states_cached_and_split(self, get):
        national = {"name": "Shared", "date": {"iso": "2026-10-01"}, "type": ["National holiday"], "locations": "All"}
        local = {"name": "Local", "date": {"iso": "2026-10-01"}, "type": ["Local holiday"], "states": [{"iso": "us-al"}]}
        get.return_value.json.return_value = {"meta": {"code": 200}, "response": {"holidays": [national, local]}}
        with tempfile.TemporaryDirectory() as cache:
            states, shared = fetch_calendar_batch(US_STATES, date(2026, 9, 29), SignalWindow(0, 30), cache_dir=cache)
            self.assertEqual(get.call_count, 1)
            self.assertNotIn("location", get.call_args.kwargs["params"])
            self.assertNotIn("month", get.call_args.kwargs["params"])
            self.assertEqual(len(shared["holidays_this_month"]), 1)
            self.assertEqual(len(states["AL"].holidays_this_month), 1)
            self.assertTrue(states["AL"].holidays_this_month[0].state_specific)
            self.assertEqual(len(states["AK"].holidays_this_month), 0)
            fetch_calendar_batch(US_STATES, date(2026, 10, 1), SignalWindow(0, 10), cache_dir=cache)
            self.assertEqual(get.call_count, 1)
            self.assertNotIn("test-key", (Path(cache) / "US_2026.json").read_text())

    @patch.dict(os.environ, {"CALENDARIFIC_API_KEY": "test-key"})
    @patch("extractors.calendar.polite_get")
    def test_observance_notes_stay_with_their_state(self, get):
        national = {"name": "National", "date": {"iso": "2026-10-01"}, "locations": "All"}
        local = {"name": "Local", "date": {"iso": "2026-10-01"}, "states": [
            {"iso": "us-al", "exception": "partly"}, {"iso": "us-ak", "exception": "optional"},
            {"iso": "us-az", "exception": "community"}, {"iso": "us-ar", "exception": None}]}
        get.return_value.json.return_value = {"meta": {"code": 200}, "response": {"holidays": [national, local]}}
        with tempfile.TemporaryDirectory() as cache:
            states, shared = fetch_calendar_batch(US_STATES, date(2026, 10, 1), SignalWindow(0, 0), cache_dir=cache)
        for code, expected in {"AL": "partly", "AK": "optional", "AZ": "community", "AR": None}.items():
            self.assertEqual(states[code].holidays_this_month[0].observance_note, expected)
        self.assertIsNone(shared["holidays_this_month"][0]["observance_note"])

    @patch.dict(os.environ, {"CALENDARIFIC_API_KEY": "test-key"})
    @patch("extractors.calendar.polite_get")
    def test_year_boundary_and_refresh(self, get):
        get.return_value.json.return_value = {"meta": {"code": 200}, "response": {"holidays": []}}
        with tempfile.TemporaryDirectory() as cache:
            fetch_calendar_batch(US_STATES, date(2026, 12, 20), SignalWindow(21, 30), cache_dir=cache)
            self.assertEqual([c.kwargs["params"]["year"] for c in get.call_args_list], [2026, 2027])
            fetch_calendar_batch(US_STATES, date(2026, 12, 20), SignalWindow(21, 30), cache_dir=cache, refresh=True)
            self.assertEqual(get.call_count, 4)

    @patch.dict(os.environ, {"TICKETMASTER_API_KEY": "test-key"})
    @patch("extractors.events.polite_get")
    def test_event_bounds_and_incomplete_results_warning(self, get):
        get.return_value.url = "https://example.com?apikey=test-key"
        get.return_value.json.return_value = {"page": {"totalElements": 75}}
        result = fetch_events(US_STATES[0], window=SignalWindow(21, 30), reference_date=date(2026, 9, 29))
        self.assertEqual(get.call_args.kwargs["params"]["localStartDateTime"], "2026-09-08T00:00:00,2026-10-29T23:59:59")
        self.assertIn("Result limit", result.meta.error)
        self.assertNotIn("test-key", result.meta.url)


class PipelineTests(unittest.TestCase):
    @patch("extractors.social.time.sleep")
    @patch("extractors.social.polite_get")
    def test_social_retries_only_the_reported_timeout_once(self, get, sleep):
        timeout = MagicMock(status_code=422, text='{"error":"Timeout. Maybe slow down a bit"}')
        invalid = MagicMock(status_code=422, text='{"error":"Invalid parameter"}')
        success = MagicMock(status_code=200, url="https://example.com/social")
        success.json.return_value = {"data": [{"title": "Local news", "subreddit": "Alabama"}]}
        for responses, error in [([timeout, success], None), ([timeout, timeout], "Timeout"),
                                 ([invalid], "Invalid parameter")]:
            with self.subTest(error=error):
                get.reset_mock()
                sleep.reset_mock()
                get.side_effect = responses
                if error:
                    with self.assertRaisesRegex(RuntimeError, error):
                        fetch_subreddit_posts(US_STATES[0])
                else:
                    self.assertEqual(len(fetch_subreddit_posts(US_STATES[0]).posts), 1)
                self.assertEqual(get.call_count, len(responses))
                if len(responses) == 2:
                    sleep.assert_called_once_with(2)
                    self.assertEqual(get.call_args_list[0], get.call_args_list[1])
                else:
                    sleep.assert_not_called()

    def test_weather_geo_survives_stitch_and_json(self):
        response = MagicMock(url='https://example.com/weather')
        response.json.return_value = {'current': {'temperature_2m': 22, 'weather_code': 0}, 'daily': {}}
        with patch('extractors.weather.polite_get', return_value=response):
            weather = fetch_weather(US_STATES[0])
        doc = stitch_state('AL', date.today(), weather=weather)
        data = doc.model_dump(mode='json')
        self.assertEqual(data['signals']['weather']['geo']['confidence'], 'exact')
        self.assertEqual(data['census_region'], 'South')
        self.assertTrue(check_batch([doc], date.today())['ok'])

    def test_state_stitch_excludes_national_sources(self):
        meta = SourceMeta(source='test', url='https://example.com', fetched_at=datetime.now(timezone.utc))
        events = EventsDoc(state_code='AL', date=date.today(), meta=meta,
                           geo=GeoTag(scope='state', state_code='AL', confidence='exact'),
                           events=[EventItem(name='Launch', venue_state='AL')])
        error = ErrorDoc(source='news', error='Unavailable', fetched_at=datetime.now(timezone.utc))
        doc = stitch_state('AL', date.today(), events=events, news=error)
        data = doc.model_dump(mode='json')
        self.assertEqual(data['signals']['events']['events'][0]['name'], 'Launch')
        self.assertTrue({'attention', 'sports', 'youtube'}.isdisjoint(data['signals']))
        self.assertIn('news', doc.sources_missing)
        self.assertEqual(set(doc.sources_present), {'events'})
        with self.assertRaises(TypeError):
            stitch_state('AL', date.today(), youtube=object())


class DateQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load definitions by name, without running notebook I/O or relying on cell numbers.
        constants = {"ALL_SOURCES", "NATIONAL_SOURCES", "COLUMNS", "ATTENTION_URL_DATE",
                     "DAY_COLS", "TIME_COLS", "INT_COLS", "FLOAT_COLS", "BOOL_COLS",
                     "CAT_COLS", "PRIMARY_KEYS", "STATE_LEVEL", "NATIONAL"}
        for name in ("json_to_tables", "data_cleaning"):
            notebook = json.loads((PIPELINE / "notebooks" / f"{name}.ipynb").read_text())
            nodes = []
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                for node in ast.parse("".join(cell["source"])).body:
                    if isinstance(node, ast.FunctionDef) or (isinstance(node, ast.Assign)
                            and all(isinstance(target, ast.Name) and target.id in constants for target in node.targets)):
                        nodes.append(node)
            namespace = {"pd": pd, "json": json, "re": re, "Counter": Counter, "WINDOWS": load_windows()}
            exec(compile(ast.Module(body=nodes, type_ignores=[]), name, "exec"), namespace)
            setattr(cls, name, namespace)

    def tables(self, publication=None, holiday=None):
        meta = {"status": "ok", "fetched_at": "2026-10-20T13:00:00Z"}
        doc = {"state_code": "AL", "date": "2026-10-20", "stitched_at": "2026-10-20T14:00:00Z",
               "signals": {"news": {"meta": meta, "articles": [{"title": "News", "seendate": publication}]},
                           "events": {"meta": meta, "events": [{"name": "Festival", "start_date": "2026-10-31"}]}}}
        if holiday is not None:
            doc["signals"]["calendar"] = {"meta": meta, "holidays_this_month": [holiday]}
        rows, expected, conflicts = self.json_to_tables["flatten"]([doc])
        tables = self.json_to_tables["build_tables"](rows)
        # Only columns needed to exercise dates; text cleaning is outside these tests.
        for table, column in {"news_article": "publisher_id", "holiday": "is_low_signal_type",
                              "reddit_post": "is_removed_title", "event": "is_package_listing",
                              "attention_article": "article_title"}.items():
            tables[table][column] = False
        return tables, expected, conflicts

    def test_missing_reference_timestamp_blocks_conversion_and_cleaning(self):
        tables, expected, conflicts = self.tables()
        tables["state_day"]["stitched_at"] = pd.NaT
        report = self.json_to_tables["run_checks"](tables, expected, conflicts)
        self.assertFalse(report.loc[report.check.eq("state_day: reference timestamps present"), "ok"].iloc[0])
        with self.assertRaisesRegex(ValueError, "Missing reference timestamp"):
            self.data_cleaning["build_candidates"](tables)

    def test_unknown_publication_date_stays_unknown(self):
        tables, _, _ = self.tables()
        candidates = self.data_cleaning["build_candidates"](tables)
        news = candidates.loc[candidates.source.eq("news")].iloc[0]
        self.assertTrue(news.is_time_unknown)
        self.assertTrue(pd.isna(news.is_within_window))
        self.assertTrue(pd.isna(news.is_available_at_reference))

    def test_future_publication_is_not_available(self):
        tables, _, _ = self.tables("2026-10-20T15:00:00Z")
        candidates = self.data_cleaning["build_candidates"](tables)
        self.assertFalse(candidates.loc[candidates.source.eq("news"), "is_available_at_reference"].iloc[0])

    def test_future_event_keeps_its_date_and_is_available(self):
        tables, _, _ = self.tables()
        candidates = self.data_cleaning["build_candidates"](tables)
        event = candidates.loc[candidates.source.eq("events")].iloc[0]
        self.assertEqual(event.event_date, pd.Timestamp("2026-10-31"))
        self.assertTrue(pd.isna(event.event_time))
        self.assertTrue(event.is_within_window)
        self.assertTrue(event.is_available_at_reference)

    def test_observance_note_survives_tables_and_candidate_context(self):
        holiday = {"name": "Celebration", "date": "2026-10-20", "type": "Local holiday",
                   "state_specific": True, "is_national": False, "observance_note": "partly"}
        tables, _, _ = self.tables(holiday=holiday)
        self.assertEqual(tables["holiday"].observance_note.iloc[0], "partly")
        candidates = self.data_cleaning["build_candidates"](tables)
        self.assertEqual(candidates.loc[candidates.source.eq("calendar"), "context"].iloc[0], "Local holiday; partly")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holiday.parquet"
            tables["holiday"].to_parquet(path, index=False)
            self.assertEqual(pd.read_parquet(path).observance_note.iloc[0], "partly")


if __name__ == "__main__":
    unittest.main()

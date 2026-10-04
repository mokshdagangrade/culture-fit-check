import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from schemas import ErrorDoc, EventItem, EventsDoc, YoutubeDoc, YoutubeVideoItem, SourceMeta, GeoTag
from stitch import stitch_state
from extractors.weather import fetch_weather
from us_states import US_STATES
from validate import check_batch

class PipelineTests(unittest.TestCase):
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

    def test_events_youtube_and_failed_source(self):
        meta = SourceMeta(source='test', url='https://example.com', fetched_at=datetime.now(timezone.utc))
        events = EventsDoc(state_code='AL', date=date.today(), meta=meta, geo=GeoTag(scope='state', state_code='AL', confidence='exact'), events=[EventItem(name='Launch', venue_state='AL')])
        youtube = YoutubeDoc(date=date.today(), meta=meta, videos=[YoutubeVideoItem(title='Video', video_id='abc')])
        error = ErrorDoc(source='news', error='Unavailable', fetched_at=datetime.now(timezone.utc))
        doc = stitch_state('AL', date.today(), events=events, youtube=youtube, news=error)
        data = doc.model_dump(mode='json')
        self.assertEqual(data['signals']['events']['events'][0]['name'], 'Launch')
        self.assertEqual(data['signals']['youtube']['scope'], 'national')
        self.assertIn('news', doc.sources_missing)
        self.assertEqual(set(doc.sources_present), {'events', 'youtube'})

if __name__ == '__main__':
    unittest.main()

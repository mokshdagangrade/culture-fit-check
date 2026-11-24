import base64
from datetime import date
from io import BytesIO
import unittest
from PIL import Image
from campaign_calendar import campaign_dates, correct_campaign_dates, calendar_instructions
from poster import extract_poster_copy, render_campaign_poster
from image_generation import build_image_prompt
from unittest.mock import MagicMock, patch
import sys


class CampaignVisualTests(unittest.TestCase):
    def test_black_friday_is_computed_for_each_year(self):
        for year, day in [(2026,27),(2027,26),(2028,24)]:
            self.assertEqual(campaign_dates('Black Friday',date(year,11,1))['Black Friday'], f'{year}-11-{day}')

    def test_calendar_cta_does_not_reuse_old_year_date(self):
        content='Our Black Friday event is almost here. Mark your calendars for November 29th.'
        self.assertIn('November 27',correct_campaign_dates(content,'Black Friday launch',date(2026,11,24)))
        self.assertNotIn('29',correct_campaign_dates(content,'Black Friday launch',date(2026,11,24)))
        self.assertIn('2026-11-27',calendar_instructions('Black Friday',date(2026,11,24)))

    def test_explicit_custom_promotion_date_is_preserved(self):
        content='Our Black Friday sale continues until November 29.'
        self.assertEqual(correct_campaign_dates(content,'Run our promotion through November 29',date(2026,11,24)),content)

    def test_unrelated_dates_are_preserved(self):
        text='A November 29 workshop. Black Friday is coming.'
        self.assertEqual(correct_campaign_dates(text,today=date(2026,11,24)),text)

    def test_poster_extracts_event_offer_date_without_weather(self):
        text='Clear skies and comfy vibes! Our Black Friday event offers up to 70% off storewide. Mark your calendars for November 27. #Brand'
        copy=extract_poster_copy(text)
        self.assertEqual(copy,{'headline':'Black Friday','offer':'up to 70% off storewide','date':'November 27'})
        self.assertNotIn('weather', str(copy))

    def test_poster_does_not_invent_discounts(self):
        copy=extract_poster_copy('Black Friday: stay tuned!')
        self.assertEqual(copy['offer'],'')
        self.assertEqual(copy['date'],'')

    def test_poster_keeps_visual_and_draws_readable_panel(self):
        visual=Image.new('RGB',(512,512),'yellow');output=BytesIO();visual.save(output,format='JPEG')
        data='data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()
        result=render_campaign_poster(data,'Black Friday: up to 70% off. November 27.','JustRight')
        poster=Image.open(BytesIO(base64.b64decode(result['poster'].split(',',1)[1])))
        self.assertEqual(poster.width,512)
        self.assertGreater(poster.height,512)
        self.assertGreater(poster.getpixel((100,100))[0],200)
        self.assertEqual(result['poster_copy']['headline'],'Black Friday')

    def test_fidelity_constraints_survive_planning(self):
        planner=MagicMock();planner.is_configured.return_value=True
        planner.call_llm.return_value='A colorful campaign with carefully balanced product photography and light.'
        refs=[{'role':'product','name':'item.png'}]
        with patch.dict(sys.modules,{'llm':planner}):
            prompt=build_image_prompt('Launch',image_references=refs)
        self.assertIn('do not bend, duplicate, fuse',prompt)
        self.assertIn('Do not copy product markings onto unrelated props',prompt)
        self.assertLessEqual(len(prompt),2048)


if __name__=='__main__':unittest.main()

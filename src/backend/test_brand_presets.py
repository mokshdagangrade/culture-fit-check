import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from seed_brand_presets import DEFAULT_FILE, read_presets, upsert_presets
from models import ProfileUpdate
from prompt_builder import build_context_prompt
from services.company_service import get_company_details


class BrandPresetTests(unittest.TestCase):
    def test_three_complete_fictional_presets(self):
        records=read_presets(DEFAULT_FILE)
        self.assertEqual(len(records),3)
        for item in records:
            self.assertTrue(item['is_fictional'])
            profile=item['profile']
            self.assertTrue(profile['states'])
            self.assertTrue(profile['past_taglines'])
            self.assertTrue(profile['brand_details']['catalog'])
            self.assertEqual(profile['brand_details']['commerce']['active_promotions'],[])
            self.assertNotIn('suggested_test_briefs',profile)
            self.assertNotIn('password',profile)
            self.assertNotIn('email',profile)

    def test_reimport_updates_by_stable_id(self):
        collection=MagicMock()
        records=read_presets(DEFAULT_FILE)
        upsert_presets(collection,records)
        upsert_presets(collection,records)
        self.assertEqual(collection.update_one.call_count,6)
        calls=collection.update_one.call_args_list
        self.assertEqual(calls[0].args[0],calls[3].args[0])
        self.assertTrue(all(c.kwargs['upsert'] for c in calls))
        self.assertTrue(all(set(c.args[0])=={'preset_id'} for c in calls))

    def test_invalid_catalog_rejected_before_import(self):
        original=json.loads(DEFAULT_FILE.read_text())
        for change in ['duplicate','nonfictional','privatefield','invalidstate']:
            payload=copy.deepcopy(original)
            if change=='duplicate':payload['brands'].append(payload['brands'][0])
            if change=='nonfictional':payload['brands'][0]['is_fictional']=False
            if change=='privatefield':payload['brands'][0]['profile']['password']='not allowed'
            if change=='invalidstate':payload['brands'][0]['profile']['states']=['Unknown']
            with self.subTest(change=change),tempfile.TemporaryDirectory() as folder:
                file=Path(folder)/'brands.json';file.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):read_presets(file)

    def test_details_flow_into_company_and_text_prompt(self):
        profile=read_presets(DEFAULT_FILE)[0]['profile']
        saved=ProfileUpdate.model_validate(profile).model_dump()
        company=get_company_details(saved)
        self.assertEqual(company['brand_details'],profile['brand_details'])
        _,prompt=build_context_prompt('Introduce the brand',company=company)
        self.assertIn('Electric coral',prompt)
        self.assertIn('MM-DAYLINE',prompt)
        self.assertIn('not active promotions',prompt)

    def test_oversized_details_rejected(self):
        with self.assertRaises(ValueError):ProfileUpdate(brand_details={'text':'x'*41000})


if __name__=='__main__':unittest.main()

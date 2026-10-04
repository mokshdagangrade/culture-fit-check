import sys
import unittest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError
import llm
from openai import APIStatusError

database = MagicMock()
with patch.dict(sys.modules, {'db': database}):
    import main
from models import GenerateRequest, ProfileUpdate

class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.user = {'_id': 'brand-a', 'business_name': 'JustRight', 'states': ['California', 'New York'], 'past_taglines': ['Made for you.']}
        database.history_collection.reset_mock()
        database.history_collection.find.return_value.sort.return_value.limit.return_value = []

    def test_profile_generation_and_persistence(self):
        with patch.object(main.llm, 'call_llm', return_value='Subject: A secret\nStay tuned.') as call:
            result = main.generate_taglines(GenerateRequest(prompt='Secret launch', content_type='email'), self.user)
        self.assertEqual(len(result.results), 2)
        for invocation in call.call_args_list:
            self.assertIn('JustRight', invocation.args[0])
            self.assertIn('Made for you.', invocation.args[0])
            self.assertIn('complete email', invocation.args[0])
        self.assertEqual(database.history_collection.insert_one.call_args.args[0]['user_id'], 'brand-a')

    def test_follow_up_and_isolation(self):
        database.history_collection.find.return_value.sort.return_value.limit.return_value = [{'prompt': 'Secret launch', 'results': []}]
        with patch.object(main.llm, 'call_llm', return_value='Coming soon.') as call:
            main.generate_taglines(GenerateRequest(prompt='give me the content', states=['California']), self.user)
        self.assertIn('Secret launch', call.call_args.args[0])
        database.history_collection.find.assert_called_with({'user_id': 'brand-a'})

    def test_regions_and_validation(self):
        self.assertEqual(len(main.regions()[0]['states']), 50)
        self.assertEqual(len(main.regions()[1]['states']), 3)
        for schema in (GenerateRequest, ProfileUpdate):
            with self.assertRaises(ValidationError):
                schema(prompt='Launch', states=['Unknown'])
        with self.assertRaises(ValidationError):
            GenerateRequest(prompt='Launch', content_type='invalid')

    def test_empty_and_truncated_provider_content(self):
        import llm
        for content, reason in [("", "stop"), ("unfinished", "length")]:
            fake = MagicMock()
            fake.chat.completions.create.return_value.choices = [
                MagicMock(message=MagicMock(content=content), finish_reason=reason)]
            with patch.object(llm, 'is_configured', return_value=True), patch.object(llm, '_client', return_value=fake):
                with self.assertRaises(llm.LLMError):
                    llm.call_llm('launch')

    def test_gemini_budget_and_high_demand_error(self):
        import llm
        from openai import APIStatusError
        fake = MagicMock()
        fake.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Subject: Launch\nMeet your new sneakers."), finish_reason="stop")]
        with patch.object(llm, 'is_configured', return_value=True), patch.object(llm, '_client', return_value=fake), patch.object(llm, 'base_url', return_value='https://generativelanguage.googleapis.com/v1beta/openai/'):
            llm.call_llm('launch', max_tokens=2048)
            self.assertEqual(fake.chat.completions.create.call_args.kwargs['reasoning_effort'], 'low')
            self.assertEqual(fake.chat.completions.create.call_args.kwargs['max_tokens'], 8192)
            response = MagicMock(status_code=503, headers={}, request=MagicMock())
            fake.chat.completions.create.side_effect = APIStatusError('private details', response=response, body=None)
            with self.assertRaisesRegex(llm.LLMError, 'high demand'):
                llm.call_llm('launch')

    def test_state_context_filters_sources_and_queries_fresh_state(self):
        from datetime import datetime, timezone
        get_context = main.get_state_context
        collection = MagicMock()
        collection.find_one.return_value = {
            'date': '2026-10-03', 'signals': {
                'weather': {'state_code': 'CA', 'meta': {'status': 'ok', 'source': 'open-meteo'},
                            'condition': 'clear sky', 'temperature_c': 22},
                'news': {'state_code': 'TX', 'meta': {'status': 'ok'}, 'articles': [{'title': 'Wrong state'}]},
                'trends': {'state_code': 'CA', 'meta': {'status': 'error'}, 'trends': [{'keyword': 'Failed'}]},
                'events': {'state_code': 'CA', 'meta': {'status': 'ok'}, 'geo': {'scope': 'national'}, 'events': [{'name': 'National'}]},
            }}
        with patch.dict(get_context.__globals__, {'state_signals_collection': collection}):
            result = get_context('California', now=datetime(2026, 10, 3, tzinfo=timezone.utc))
            self.assertEqual(set(result), {'weather'})
            self.assertEqual(result['weather']['data']['temperature_c'], 22)
            query = collection.find_one.call_args.args[0]
            self.assertEqual(query['state_code'], 'CA')
            self.assertEqual(query['date']['$gte'], '2026-10-02')
            collection.reset_mock()
            self.assertEqual(get_context('Delhi'), {})
            collection.find_one.assert_not_called()

    def test_regional_context_reaches_prompt_and_result(self):
        context = {'weather': {'data': {'condition': 'rain'}, 'date': '2026-10-03'}}
        with patch.object(main, 'get_state_context', return_value=context), patch.object(main.llm, 'call_llm', return_value='Rain-ready.') as call:
            result = main.generate_for_state(self.user, 'caption', 'Launch', 'California', [])
        self.assertIn('rain', call.call_args.args[0])
        self.assertEqual(result.grounding_context, context)

    def test_hf_unsupported_model_error(self):
        fake = MagicMock()
        fake.chat.completions.create.side_effect = APIStatusError('unsupported', response=MagicMock(status_code=400, headers={}, request=MagicMock()), body={'code': 'model_not_supported'})
        with patch.object(llm, 'is_configured', return_value=True), patch.object(llm, '_client', return_value=fake):
            with self.assertRaisesRegex(llm.LLMError, 'enabled Hugging Face providers'):
                llm.call_llm('launch')

    def test_social_and_national_context_are_labeled(self):
        from datetime import datetime, timezone
        collection = MagicMock()
        collection.find_one.return_value = {'date': '2026-10-03', 'signals': {
            'social': {'state_code': 'AL', 'geo': {'scope': 'state', 'confidence': 'guessed'}, 'meta': {'status': 'ok'}, 'subreddit_confirmed': True, 'posts': [{'title': 'Beach activities', 'url': 'private-url'}]},
            'sports': {'scope': 'national', 'meta': {'status': 'ok'}, 'events': [{'home_team': 'A'}]},
            'attention': {'scope': 'national', 'meta': {'status': 'empty'}, 'top_articles': []}}}
        with patch.dict(main.get_state_context.__globals__, {'state_signals_collection': collection}):
            context = main.get_state_context('Alabama', datetime(2026, 10, 3, tzinfo=timezone.utc))
            self.assertEqual(set(context), {'social', 'sports'})
            self.assertEqual(context['social']['confidence'], 'guessed')
            self.assertEqual(context['sports']['scope'], 'national')
            self.assertNotIn('url', context['social']['data']['posts'][0])
            collection.find_one.return_value['signals']['social']['subreddit_confirmed'] = False
            self.assertNotIn('social', main.get_state_context('Alabama'))

    def test_email_requires_observed_weather_hook(self):
        context = {'weather': {'data': {'condition': 'overcast', 'temperature_c': 27}, 'date': '2026-10-03'}}
        with patch.object(main, 'get_state_context', return_value=context), patch.object(main.llm, 'call_llm', return_value='Cloudy skies, fresh steps.') as call:
            main.generate_for_state(self.user, 'email', 'Weekend sale', 'Alabama', [])
        prompt = call.call_args.args[0]
        system = call.call_args.kwargs['system']
        self.assertIn('overcast', prompt)
        self.assertIn('WEATHER ADAPTATION REQUIREMENT', system)
        self.assertIn('opening body paragraph', system)
        self.assertIn('not a whole-state or upcoming-weekend forecast', system)
        with patch.object(main, 'get_state_context', return_value={}), patch.object(main.llm, 'call_llm', return_value='Fresh steps.') as call:
            main.generate_for_state(self.user, 'email', 'Weekend sale', 'Alabama', [])
        self.assertNotIn('WEATHER ADAPTATION REQUIREMENT', call.call_args.kwargs['system'])

    def test_new_launch_excludes_old_sale_and_keeps_followup(self):
        old = [{'prompt': 'Weekend flash sale', 'content_type': 'email', 'results': [{'text': 'Shop old-sale.example'}]}]
        with patch.object(main, 'get_state_context', return_value={}), patch.object(main.llm, 'call_llm', return_value='Introducing DIY peel-off sneakers.') as call:
            main.generate_for_state(self.user, 'email', 'new launch about diy peel off sneakers', 'Alabama', old)
        prompt = call.call_args.args[0]
        self.assertNotIn('old-sale.example', prompt)
        self.assertNotIn('Weekend flash sale', prompt)
        self.assertIn('new launch about diy peel off sneakers', prompt)
        self.assertIn('A new launch must announce that product', call.call_args.kwargs['system'])
        launch = {'prompt': 'new launch about diy peel off sneakers', 'content_type': 'email', 'results': []}
        self.assertEqual(main.campaign_history('make it shorter', old + [launch]), [launch])

    def test_chat_requires_auth(self):
        route = next(r for r in main.app.routes if r.path == '/chat')
        self.assertTrue(any(d.call == main.get_current_user for d in route.dependant.dependencies))

if __name__ == '__main__':
    unittest.main()

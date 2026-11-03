import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from image_generation import generate_image, build_image_prompt, ImageGenerationError, cloudflare_error_reason


class HostedImageTests(unittest.TestCase):
    def setUp(self):
        text_provider = MagicMock()
        text_provider.is_configured.return_value = False
        modules = patch.dict(sys.modules, {'llm': text_provider})
        modules.start()
        self.addCleanup(modules.stop)
        env = patch.dict(os.environ, {'FLUX_KEY': ''})
        env.start()
        self.addCleanup(env.stop)

    def test_fallback_does_not_choose_products_or_season_for_brand(self):
        prompt = build_image_prompt('Book a relaxing retreat', {'products': 'wellness treatments', 'tone': 'calm'},
                                    'Watercolor style in muted blue', 'Use our lake setting')
        for fact in ['wellness treatments', 'muted blue', 'lake setting', 'relaxing retreat']:
            self.assertIn(fact, prompt)
        for assumption in ['sneaker', 'gift box', 'holiday', 'burgundy', 'photography']:
            self.assertNotIn(assumption, prompt)

    def test_planner_receives_caption_brief_brand_and_project(self):
        planner = sys.modules['llm']
        planner.is_configured.return_value = True
        planner.call_llm.return_value = 'An abstract watercolor landscape in muted blue with a calm lakeside focal point.'
        build_image_prompt('A quiet escape', {'target_audience': 'busy parents'},
                           'Promote a lakeside retreat', 'Brand palette: muted blue; avoid city scenes')
        import json
        data = json.loads(planner.call_llm.call_args.args[0])
        self.assertEqual(data['selected_caption'], 'A quiet escape')
        self.assertEqual(data['original_campaign_brief'], 'Promote a lakeside retreat')
        self.assertEqual(data['brand_details']['target_audience'], 'busy parents')
        self.assertIn('muted blue', data['project_references_and_preferences'])

    def test_art_director_uses_brand_facts(self):
        planner = sys.modules['llm']
        planner.is_configured.return_value = True
        planner.call_llm.return_value = 'A sneaker silhouette inside a partly opened gift box, warm rim lighting and a clean backdrop.'
        prompt = build_image_prompt('A holiday sneak peek', {'products': 'DIY sneakers'})
        self.assertIn('gift box', prompt)
        self.assertIn('DIY sneakers', planner.call_llm.call_args.args[0])
        self.assertLessEqual(len(prompt), 2048)

    def test_planner_failure_falls_back_without_failing_image(self):
        planner = sys.modules['llm']
        planner.is_configured.return_value = True
        planner.call_llm.side_effect = RuntimeError('quota')
        self.assertIn('Sneaker launch', build_image_prompt('Sneaker launch'))

    def test_brand_mark_rules_survive_planning_and_fallback(self):
        planner = sys.modules['llm']
        for configured in (False, True):
            with self.subTest(planner_configured=configured):
                planner.is_configured.return_value = configured
                planner.call_llm.return_value = 'A product on a clean backdrop with dramatic lighting. ' * 30
                prompt = build_image_prompt('New collection ' * 300, {'products': 'athletic shoes'})
                self.assertIn('generic and unbranded', prompt)
                self.assertIn('No third-party trademarks', prompt)
                self.assertIn('render no logos or lettering.', prompt)
                self.assertLessEqual(len(prompt), 2048)

    def test_uploaded_logo_is_reserved_for_exact_placement(self):
        prompt = build_image_prompt('New collection', logo_available=True)
        self.assertIn('only that exact uploaded asset', prompt)
        self.assertIn('never invent, imitate or redraw', prompt)
        self.assertIn('balanced clear space', prompt)
        self.assertLessEqual(len(prompt), 2048)

    def test_uploaded_logo_is_sent_as_reference_not_overlaid(self):
        with patch('image_generation.validate_logo') as validate, \
             patch('image_generation._generate_image', return_value={'image':'composed-image','model':'test'}) as generate:
            result = generate_image('Campaign', logo_data='uploaded-logo')
        validate.assert_called_once_with('uploaded-logo')
        self.assertEqual(generate.call_args.kwargs['image_references'],
                         [{'role':'logo','name':'Approved brand logo','data':'uploaded-logo'}])
        self.assertEqual(result['image'], 'composed-image')

    def test_reference_images_are_sent_as_multipart_to_edit_model(self):
        import base64
        requests = MagicMock()
        response=requests.post.return_value
        response.status_code=200
        response.json.return_value={'success':True,'result':{'image':base64.b64encode(b'\xff\xd8\xfftest').decode()}}
        refs=[{'name':'shoe.png','role':'product','data':'product-input'},
              {'name':'palette.png','role':'style','data':'style-input'}]
        with patch.dict(sys.modules, {'requests':requests}), \
             patch.dict(os.environ, {'FLUX_KEY':'cf-test','CLOUDFLARE_ACCOUNT_ID':'abc123'}), \
             patch('image_generation.validate_logo'), \
             patch('image_generation.prepare_reference', side_effect=[b'product-bytes',b'style-bytes']):
            result=generate_image('Campaign', image_references=refs)
        kwargs=requests.post.call_args.kwargs
        self.assertEqual(result['model'], '@cf/black-forest-labs/flux-2-klein-4b')
        self.assertEqual(kwargs['files']['input_image_0'][1], b'product-bytes')
        self.assertEqual(kwargs['files']['input_image_1'][1], b'style-bytes')
        self.assertIn('Image 0: use this actual product', kwargs['data']['prompt'])
        self.assertIn('Image 1: use its palette', kwargs['data']['prompt'])
        self.assertNotIn('json',kwargs)

    def test_references_cannot_silently_fall_back_to_text_only(self):
        with patch('image_generation.validate_logo'), patch.dict(os.environ, {'FLUX_KEY':'','HF_TOKEN':'test'}):
            with self.assertRaisesRegex(ImageGenerationError, 'will not be ignored'):
                generate_image('Campaign',image_references=[{'role':'product','data':'input'}])

    def test_too_many_references_are_rejected(self):
        with self.assertRaisesRegex(ImageGenerationError, 'up to three'):
            generate_image('Campaign',image_references=[{'role':'product','data':'input'}]*5)

    def test_invalid_logo_is_rejected_before_inference(self):
        with patch('image_generation.validate_logo', side_effect=ValueError('Invalid logo')), \
             patch('image_generation._generate_image') as generate:
            with self.assertRaisesRegex(ImageGenerationError, 'Invalid logo'):
                generate_image('Campaign', logo_data='bad-logo')
        generate.assert_not_called()

    def test_cloudflare_bad_request_has_status_and_safe_code(self):
        requests = MagicMock()
        response=requests.post.return_value
        response.status_code=400
        response.json.return_value={'errors':[{'code':5006,'message':'private payload and secret'}]}
        with patch.dict(sys.modules, {'requests':requests}), patch.dict(os.environ, {'FLUX_KEY':'secret','CLOUDFLARE_ACCOUNT_ID':'abc123'}):
            with self.assertRaisesRegex(ImageGenerationError, 'HTTP 400') as caught:
                generate_image('Campaign')
        self.assertIn('5006', str(caught.exception))
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('private', str(caught.exception))

    def test_cloudflare_timeout_is_distinct(self):
        requests=MagicMock()
        ReadTimeout=type('ReadTimeout',(Exception,),{})
        requests.post.side_effect=ReadTimeout('private credentials')
        with patch.dict(sys.modules, {'requests':requests}), patch.dict(os.environ, {'FLUX_KEY':'secret','CLOUDFLARE_ACCOUNT_ID':'abc123'}):
            with self.assertRaisesRegex(ImageGenerationError, 'timed out'):
                generate_image('Campaign')

    def test_shared_error_code_does_not_assume_moderation(self):
        self.assertEqual(cloudflare_error_reason([{'code':3030,'message':'Unknown runtime error'}]), '')
        filtered=cloudflare_error_reason([{'code':3030,'message':'Your output has been flagged'}])
        self.assertIn('content review', filtered)
        self.assertNotIn('Your output has been flagged', filtered)
        validation=cloudflare_error_reason([{'code':3030,'message':'prompt is required'}])
        self.assertIn('prompt format or length', validation)

    def test_cloudflare_missing_account(self):
        with patch.dict(os.environ, {'FLUX_KEY': 'test', 'CLOUDFLARE_ACCOUNT_ID': ''}):
            with self.assertRaisesRegex(ImageGenerationError, 'CLOUDFLARE_ACCOUNT_ID'):
                generate_image('Campaign')

    def test_cloudflare_remote_generation(self):
        import base64
        requests = MagicMock()
        response = requests.post.return_value
        response.status_code = 200
        response.json.return_value = {'success': True, 'result': {'image': base64.b64encode(b'\xff\xd8\xfftest').decode()}}
        with patch.dict(sys.modules, {'requests': requests}), patch.dict(os.environ, {'FLUX_KEY': 'cf-secret', 'CLOUDFLARE_ACCOUNT_ID': 'abc123'}):
            result = generate_image('A campaign ' * 1000)
        self.assertEqual(result['model'], '@cf/black-forest-labs/flux-1-schnell')
        self.assertLessEqual(len(result['prompt']), 2048)
        self.assertEqual(requests.post.call_args.kwargs['headers']['Authorization'], 'Bearer cf-secret')

    def test_cloudflare_rejected_credentials_are_not_leaked(self):
        requests = MagicMock()
        requests.post.return_value.status_code = 403
        with patch.dict(sys.modules, {'requests': requests}), patch.dict(os.environ, {'FLUX_KEY': 'cf-secret', 'CLOUDFLARE_ACCOUNT_ID': 'abc123'}):
            with self.assertRaises(ImageGenerationError) as caught:
                generate_image('Campaign')
        self.assertNotIn('cf-secret', str(caught.exception))
        self.assertIn('Workers AI access', str(caught.exception))

    def test_missing_token(self):
        with patch.dict(os.environ, {'HF_TOKEN': ''}):
            with self.assertRaisesRegex(ImageGenerationError, 'Set HF_TOKEN'):
                generate_image('Campaign')

    def test_remote_inference_and_encoded_result(self):
        hub = MagicMock()
        pil = MagicMock()
        image = pil.ImageOps.exif_transpose.return_value.convert.return_value
        image.save.side_effect = lambda output, **kwargs: output.write(b'jpeg bytes')
        with patch.dict(sys.modules, {'huggingface_hub': hub, 'PIL': pil}), patch.dict(os.environ, {'HF_TOKEN': 'test-token', 'HF_IMAGE_MODEL': 'test/model', 'HF_IMAGE_PROVIDER': 'auto'}):
            result = generate_image('New collection', 'Brand', 'California')
        hub.InferenceClient.assert_called_once_with(provider='auto', api_key='test-token', timeout=120)
        kwargs = hub.InferenceClient.return_value.text_to_image.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test/model')
        self.assertTrue(result['image'].startswith('data:image/jpeg;base64,'))
        self.assertIn('New collection', result['prompt'])

    def test_payment_required_does_not_assume_credits_were_used(self):
        hub = MagicMock()
        error = RuntimeError('provider payment error')
        error.response = MagicMock(status_code=402)
        hub.InferenceClient.return_value.text_to_image.side_effect = error
        with patch.dict(sys.modules, {'huggingface_hub': hub, 'PIL': MagicMock()}), patch.dict(os.environ, {'HF_TOKEN': 'test-token'}):
            with self.assertRaisesRegex(ImageGenerationError, 'requires payment') as caught:
                generate_image('Campaign')
        self.assertNotIn('exhausted', str(caught.exception))

    def test_provider_error_does_not_leak_credentials(self):
        hub = MagicMock()
        error = RuntimeError('secret-token provider payload')
        error.response = MagicMock(status_code=403)
        hub.InferenceClient.return_value.text_to_image.side_effect = error
        with patch.dict(sys.modules, {'huggingface_hub': hub, 'PIL': MagicMock()}), patch.dict(os.environ, {'HF_TOKEN': 'secret-token'}):
            with self.assertRaises(ImageGenerationError) as caught:
                generate_image('Campaign')
        self.assertNotIn('secret-token', str(caught.exception))
        self.assertIn('permissions', str(caught.exception))


if __name__ == '__main__':
    unittest.main()

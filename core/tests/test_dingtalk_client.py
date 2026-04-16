from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from core.services import dingtalk_client


class DingTalkClientTokenTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    @override_settings(
        DINGTALK={
            'CLIENT_ID': 'cid_demo',
            'CLIENT_SECRET': 'secret_demo',
        }
    )
    @patch('core.services.dingtalk_client.requests.post')
    def test_fetch_openapi_app_token_uses_internal_app_endpoint(self, mocked_post):
        mocked_post.return_value.ok = True
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            'accessToken': 'token_demo',
            'expireIn': 7200,
        }

        token, expires_in = dingtalk_client._fetch_openapi_app_token()

        self.assertEqual(token, 'token_demo')
        self.assertEqual(expires_in, 7200)
        mocked_post.assert_called_once_with(
            'https://api.dingtalk.com/v1.0/oauth2/accessToken',
            json={
                'appKey': 'cid_demo',
                'appSecret': 'secret_demo',
            },
            timeout=10,
        )

    @override_settings(
        DINGTALK={
            'CLIENT_ID': 'cid_demo',
            'CLIENT_SECRET': 'secret_demo',
        }
    )
    @patch('core.services.dingtalk_client.requests.post')
    def test_refresh_openapi_token_caches_access_token(self, mocked_post):
        cache.clear()
        mocked_post.return_value.ok = True
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            'accessToken': 'token_cached',
            'expireIn': 7200,
        }

        token, _ = dingtalk_client.refresh_app_access_token(kind='openapi')

        self.assertEqual(token, 'token_cached')
        self.assertEqual(cache.get('dingtalk_app_access_token:openapi'), 'token_cached')

    @override_settings(
        DINGTALK={
            'CLIENT_ID': 'cid_demo',
            'CLIENT_SECRET': 'secret_demo',
        }
    )
    @patch('core.services.dingtalk_client.requests.post')
    def test_fetch_openapi_app_token_error_contains_code_and_message(self, mocked_post):
        mocked_post.return_value.ok = False
        mocked_post.return_value.status_code = 403
        mocked_post.return_value.json.return_value = {
            'code': 'Forbidden.AccessDenied.AccessTokenPermissionDenied',
            'message': 'Permission denied',
        }

        with self.assertRaises(RuntimeError) as ctx:
            dingtalk_client._fetch_openapi_app_token()

        message = str(ctx.exception)
        self.assertIn('Forbidden.AccessDenied.AccessTokenPermissionDenied', message)
        self.assertIn('Permission denied', message)

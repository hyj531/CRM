from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class DingTalkAuthConfigTests(APITestCase):
    @override_settings(
        DINGTALK={
            'CLIENT_ID': 'cid_demo',
            'CLIENT_SECRET': 'secret_demo',
            'CORP_ID': 'ding_corp_demo',
            'TOKEN_URL': 'https://api.dingtalk.com/v1.0/oauth2/userAccessToken',
            'USERINFO_URL': 'https://api.dingtalk.com/v1.0/contact/users/{unionId}',
        }
    )
    def test_dingtalk_auth_config_allow_anonymous_and_enabled(self):
        response = self.client.get(reverse('dingtalk_auth_config'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('enabled'), True)
        self.assertEqual(response.data.get('corp_id'), 'ding_corp_demo')

    @override_settings(
        DINGTALK={
            'CLIENT_ID': 'cid_demo',
            'CLIENT_SECRET': 'secret_demo',
            'CORP_ID': 'ding_corp_demo',
            'TOKEN_URL': '',
            'USERINFO_URL': 'https://api.dingtalk.com/v1.0/contact/users/{unionId}',
        }
    )
    def test_dingtalk_auth_config_disabled_when_required_setting_missing(self):
        response = self.client.get(reverse('dingtalk_auth_config'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('enabled'), False)
        self.assertEqual(response.data.get('corp_id'), 'ding_corp_demo')

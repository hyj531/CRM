from dataclasses import dataclass

import requests
from django.conf import settings

@dataclass
class DingTalkUserInfo:
    user_id: str
    name: str
    email: str = ''
    mobile: str = ''
    union_id: str = ''


def _get_setting(key):
    return settings.DINGTALK.get(key, '')


def _require_setting(key):
    value = _get_setting(key)
    if not value:
        raise RuntimeError(f'DingTalk setting {key} is required')
    return value


def fetch_user_by_code(code):
    mock_user_id = _get_setting('MOCK_USER_ID')
    if mock_user_id:
        return DingTalkUserInfo(user_id=mock_user_id, name=mock_user_id)

    token_url = _require_setting('TOKEN_URL')
    userinfo_url = _require_setting('USERINFO_URL')
    client_id = _require_setting('CLIENT_ID')
    client_secret = _require_setting('CLIENT_SECRET')

    token_resp = requests.post(
        token_url,
        json={'client_id': client_id, 'client_secret': client_secret, 'code': code},
        timeout=10,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = token_data.get('access_token') or token_data.get('token')
    if not access_token:
        raise RuntimeError('Failed to obtain access token from DingTalk')

    user_resp = requests.get(
        userinfo_url,
        params={'access_token': access_token, 'code': code},
        timeout=10,
    )
    user_resp.raise_for_status()
    user_data = user_resp.json()

    return DingTalkUserInfo(
        user_id=str(user_data.get('userid') or user_data.get('user_id') or ''),
        name=user_data.get('name') or '',
        email=user_data.get('email') or '',
        mobile=user_data.get('mobile') or '',
        union_id=str(user_data.get('unionid') or user_data.get('union_id') or ''),
    )


def fetch_departments():
    sync_file = _get_setting('SYNC_FILE')
    if sync_file:
        return None

    dept_url = _require_setting('DEPT_LIST_URL')
    access_token = _require_setting('ACCESS_TOKEN')
    response = requests.get(dept_url, params={'access_token': access_token}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get('departments') or payload.get('department') or []


def fetch_department_users(dept_id):
    user_url = _require_setting('USER_LIST_URL')
    access_token = _require_setting('ACCESS_TOKEN')
    response = requests.get(user_url, params={'access_token': access_token, 'dept_id': dept_id}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get('users') or payload.get('userlist') or []

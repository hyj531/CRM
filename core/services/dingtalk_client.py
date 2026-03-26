from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

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


def _is_openapi_url(url):
    return 'api.dingtalk.com/v1.0' in url


def _extract_access_token(payload):
    return payload.get('access_token') or payload.get('token') or payload.get('accessToken')


def _get_app_token_cache_key(kind):
    return f'dingtalk_app_access_token:{kind}'


def _cache_app_token(kind, token, expires_in):
    if not token:
        return token
    try:
        ttl = int(expires_in)
    except (TypeError, ValueError):
        ttl = 0
    # Refresh a bit earlier to avoid edge expiry during calls.
    ttl = max(ttl - 120, 60) if ttl > 0 else 3600
    cache.set(_get_app_token_cache_key(kind), token, timeout=ttl)
    return token


def _fetch_openapi_app_token():
    corp_id = _require_setting('CORP_ID')
    client_id = _require_setting('CLIENT_ID')
    client_secret = _require_setting('CLIENT_SECRET')
    token_url = f'https://api.dingtalk.com/v1.0/oauth2/{corp_id}/token'
    resp = requests.post(
        token_url,
        json={
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials',
        },
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = _extract_access_token(payload)
    if not token:
        raise RuntimeError('Failed to obtain app access token from DingTalk OpenAPI')
    expires_in = payload.get('expires_in') or payload.get('expireIn') or 7200
    return token, expires_in


def _fetch_oapi_app_token():
    client_id = _require_setting('CLIENT_ID')
    client_secret = _require_setting('CLIENT_SECRET')
    resp = requests.get(
        'https://oapi.dingtalk.com/gettoken',
        params={'appkey': client_id, 'appsecret': client_secret},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload.get('access_token') or payload.get('token')
    if not token:
        raise RuntimeError('Failed to obtain app access token from DingTalk OAPI')
    expires_in = payload.get('expires_in') or 7200
    return token, expires_in


def _get_app_access_token_for_url(url):
    manual_token = _get_setting('ACCESS_TOKEN')
    if manual_token:
        return manual_token

    kind = 'openapi' if _is_openapi_url(url) else 'oapi'
    cache_key = _get_app_token_cache_key(kind)
    cached = cache.get(cache_key)
    if cached:
        return cached

    if kind == 'openapi':
        token, expires_in = _fetch_openapi_app_token()
    else:
        token, expires_in = _fetch_oapi_app_token()
    return _cache_app_token(kind, token, expires_in)


def fetch_user_by_code(code):
    mock_user_id = _get_setting('MOCK_USER_ID')
    if mock_user_id:
        return DingTalkUserInfo(user_id=mock_user_id, name=mock_user_id)

    token_url = _require_setting('TOKEN_URL')
    userinfo_url = _require_setting('USERINFO_URL')
    client_id = _require_setting('CLIENT_ID')
    client_secret = _require_setting('CLIENT_SECRET')

    token_payload = {'client_id': client_id, 'client_secret': client_secret, 'code': code}
    if 'userAccessToken' in token_url or _is_openapi_url(token_url):
        token_payload = {
            'clientId': client_id,
            'clientSecret': client_secret,
            'code': code,
            'grantType': 'authorization_code',
        }
    elif 'gettoken' in token_url:
        token_payload = {'appkey': client_id, 'appsecret': client_secret}

    token_resp = requests.post(token_url, json=token_payload, timeout=10)
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = _extract_access_token(token_data)
    if not access_token:
        raise RuntimeError('Failed to obtain access token from DingTalk')

    user_headers = {}
    user_params = None
    user_url = userinfo_url
    if _is_openapi_url(userinfo_url):
        user_headers = {'x-acs-dingtalk-access-token': access_token}
        union_id = token_data.get('unionId') or token_data.get('union_id')
        if '{unionId}' in userinfo_url or '{union_id}' in userinfo_url:
            if not union_id:
                raise RuntimeError('unionId is required to fetch user info')
            user_url = userinfo_url.replace('{unionId}', str(union_id)).replace('{union_id}', str(union_id))
        user_params = None
    else:
        user_params = {'access_token': access_token, 'code': code}

    user_resp = requests.get(user_url, params=user_params, headers=user_headers, timeout=10)
    user_resp.raise_for_status()
    user_data = user_resp.json()

    return DingTalkUserInfo(
        user_id=str(
            user_data.get('userid')
            or user_data.get('user_id')
            or user_data.get('unionid')
            or user_data.get('union_id')
            or user_data.get('openId')
            or ''
        ),
        name=user_data.get('name') or user_data.get('nick') or user_data.get('nickName') or '',
        email=user_data.get('email') or user_data.get('emailAddress') or '',
        mobile=user_data.get('mobile') or user_data.get('mobilePhone') or '',
        union_id=str(user_data.get('unionid') or user_data.get('union_id') or ''),
    )


def fetch_departments():
    sync_file = _get_setting('SYNC_FILE')
    if sync_file:
        return None

    dept_url = _require_setting('DEPT_LIST_URL')
    access_token = _get_app_access_token_for_url(dept_url)
    if _is_openapi_url(dept_url):
        response = requests.get(
            dept_url,
            headers={'x-acs-dingtalk-access-token': access_token},
            timeout=10,
        )
    else:
        response = requests.get(dept_url, params={'access_token': access_token}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get('departments') or payload.get('department') or []


def fetch_department_users(dept_id):
    user_url = _require_setting('USER_LIST_URL')
    access_token = _get_app_access_token_for_url(user_url)
    if _is_openapi_url(user_url):
        response = requests.get(
            user_url,
            params={'dept_id': dept_id},
            headers={'x-acs-dingtalk-access-token': access_token},
            timeout=10,
        )
    else:
        response = requests.get(user_url, params={'access_token': access_token, 'dept_id': dept_id}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get('users') or payload.get('userlist') or []

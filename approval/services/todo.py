import logging

import requests
from django.conf import settings

from core.services import dingtalk_client

logger = logging.getLogger(__name__)


DEFAULT_FRONTEND_BASE_URL = 'http://127.0.0.1:5173/app'
DEFAULT_OWN_OA_CREATE_URL = 'https://oapi.dingtalk.com/topapi/process/own_oa/instance/create'


def _get_setting(key, default=''):
    config = getattr(settings, 'DINGTALK', {}) or {}
    return config.get(key, default)


def _get_frontend_base_url():
    return getattr(settings, 'FRONTEND_BASE_URL', DEFAULT_FRONTEND_BASE_URL) or DEFAULT_FRONTEND_BASE_URL


def build_task_url(task_id):
    base = _get_frontend_base_url().rstrip('/')
    return f"{base}/approvals/tasks/{task_id}"


def _format_url(template, user_id=None, union_id=None, operator_union_id=None, task_id=None):
    if not template:
        return template
    replacements = {
        '{userId}': user_id,
        '{userid}': user_id,
        '{user_id}': user_id,
        '{unionId}': union_id,
        '{unionid}': union_id,
        '{union_id}': union_id,
        '{operatorUnionId}': operator_union_id,
        '{operatorunionid}': operator_union_id,
        '{operator_union_id}': operator_union_id,
        '{taskId}': task_id,
        '{taskid}': task_id,
        '{task_id}': task_id,
    }
    for key, value in replacements.items():
        if value is not None:
            template = template.replace(key, str(value))
    return template


def _send_request(url, payload):
    access_token = dingtalk_client._get_app_access_token_for_url(url)
    if not access_token:
        raise RuntimeError('DingTalk access token unavailable')

    if dingtalk_client._is_openapi_url(url):
        headers = {'x-acs-dingtalk-access-token': access_token}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
    else:
        response = requests.post(url, params={'access_token': access_token}, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def send_todo_task(user, title, content, url=None, source_id=None, originator=None):
    if str(_get_setting('TODO_ENABLED', '')).lower() not in ('1', 'true', 'yes'):
        logger.info('DingTalk todo disabled; skip sending: %s', title)
        return False

    process_code = _get_setting('OWN_OA_PROCESS_CODE')
    if process_code:
        return _send_own_oa_task(
            originator=originator or user,
            assignee=user,
            process_code=process_code,
            title=title,
            content=content,
            url=url,
            source_id=source_id,
        )

    create_url = _get_setting('TODO_CREATE_URL')
    if not create_url:
        logger.info('DingTalk todo create url not configured; skip sending: %s', title)
        return False

    user_id = getattr(user, 'dingtalk_user_id', None) or getattr(user, 'dingtalk_user', None)
    union_id = getattr(user, 'dingtalk_union_id', None) or getattr(user, 'dingtalk_union', None)
    operator_union_id = _get_setting('TODO_OPERATOR_UNION_ID') or union_id
    if not user_id and not union_id:
        logger.info('User missing DingTalk user id; skip todo send for %s', getattr(user, 'username', ''))
        return False

    create_url = _format_url(
        create_url,
        user_id=user_id,
        union_id=union_id,
        operator_union_id=operator_union_id,
    )
    task_url = url or ''
    payload = {
        'sourceId': source_id or f'approval-task-{user_id}-{title}',
        'subject': title,
        'description': content,
        'detailUrl': {
            'pcUrl': task_url,
            'mobileUrl': task_url,
        },
    }

    # Some DingTalk gateways expect the executor in payload when url is not user-scoped.
    if '{userId}' not in create_url and '{userid}' not in create_url and '{user_id}' not in create_url:
        payload['executorId'] = str(user_id)

    try:
        _send_request(create_url, payload)
        return True
    except Exception as exc:
        logger.warning('Failed to create DingTalk todo: %s', exc)
        return False


def _send_own_oa_task(originator, assignee, process_code, title, content, url=None, source_id=None):
    create_url = _get_setting('OWN_OA_CREATE_URL') or DEFAULT_OWN_OA_CREATE_URL
    originator_id = getattr(originator, 'dingtalk_user_id', None)
    assignee_id = getattr(assignee, 'dingtalk_user_id', None)
    if not originator_id or not assignee_id:
        logger.info('Missing DingTalk user id for own_oa task; skip sending.')
        return False

    form_label = _get_setting('OWN_OA_FORM_LABEL') or '审批详情'
    biz_id = source_id or f'approval-task-{assignee_id}-{title}'
    task_url = url or ''

    payload = {
        'process_code': process_code,
        'title': title,
        'originator_user_id': originator_id,
        'approvers': [
            {
                'user_id': assignee_id,
                'task_url': task_url,
                'mobile_task_url': task_url,
            }
        ],
        'form_values': {
            form_label: content or '点击查看审批详情',
        },
        'biz_id': biz_id,
        'remark': f'业务单号：{biz_id}',
    }

    try:
        _send_request(create_url, payload)
        return True
    except Exception as exc:
        logger.warning('Failed to create DingTalk own_oa approval: %s', exc)
        return False


def complete_todo_task(user, source_id=None, task_id=None):
    complete_url = _get_setting('TODO_COMPLETE_URL')
    if not complete_url:
        return False
    user_id = getattr(user, 'dingtalk_user_id', None) or getattr(user, 'dingtalk_user', None)
    union_id = getattr(user, 'dingtalk_union_id', None) or getattr(user, 'dingtalk_union', None)
    operator_union_id = _get_setting('TODO_OPERATOR_UNION_ID') or union_id
    if not user_id and not union_id:
        return False

    complete_url = _format_url(
        complete_url,
        user_id=user_id,
        union_id=union_id,
        operator_union_id=operator_union_id,
        task_id=task_id,
    )
    payload = {
        'sourceId': source_id,
    }
    if '{userId}' not in complete_url and '{userid}' not in complete_url and '{user_id}' not in complete_url:
        payload['executorId'] = str(user_id)

    try:
        _send_request(complete_url, payload)
        return True
    except Exception as exc:
        logger.warning('Failed to complete DingTalk todo: %s', exc)
        return False

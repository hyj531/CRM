import logging
from dataclasses import dataclass
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from approval import models
from core import models as core_models
from core.services import dingtalk_client

logger = logging.getLogger(__name__)


DEFAULT_FRONTEND_BASE_URL = 'http://127.0.0.1:5173/app'
DEFAULT_OWN_OA_CREATE_URL = 'https://oapi.dingtalk.com/topapi/process/own_oa/instance/create'
RETRY_DELAYS_SECONDS = [30, 120, 600, 1800, 7200]


@dataclass
class TodoGatewayResult:
    ok: bool
    channel: str
    task_id: str = ''
    error: str = ''
    raw: dict | None = None


def _get_setting(key, default=''):
    config = getattr(settings, 'DINGTALK', {}) or {}
    return config.get(key, default)


def _is_todo_enabled():
    return str(_get_setting('TODO_ENABLED', '')).lower() in ('1', 'true', 'yes')


def _resolve_channel():
    if not _is_todo_enabled():
        return models.ApprovalTask.TODO_CHANNEL_DISABLED
    if _get_setting('OWN_OA_PROCESS_CODE'):
        return models.ApprovalTask.TODO_CHANNEL_OWN_OA
    if _get_setting('TODO_CREATE_URL'):
        return models.ApprovalTask.TODO_CHANNEL_TODO_API
    return models.ApprovalTask.TODO_CHANNEL_DISABLED


def _get_frontend_base_url():
    return getattr(settings, 'FRONTEND_BASE_URL', DEFAULT_FRONTEND_BASE_URL) or DEFAULT_FRONTEND_BASE_URL


def build_todo_source_id(task_id):
    return f'approval-task-{task_id}'


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


def _template_has_user_id(template):
    if not template:
        return False
    return any(key in template for key in ('{userId}', '{userid}', '{user_id}'))


def _template_has_task_id(template):
    if not template:
        return False
    return any(key in template for key in ('{taskId}', '{taskid}', '{task_id}'))


def _has_unresolved_placeholder(value):
    return bool(value) and ('{' in value and '}' in value)


def _send_request(url, payload, method='post'):
    access_token = dingtalk_client._get_app_access_token_for_url(url)
    if not access_token:
        raise RuntimeError('DingTalk access token unavailable')

    method = (method or 'post').lower()
    if dingtalk_client._is_openapi_url(url):
        headers = {'x-acs-dingtalk-access-token': access_token}
        if method == 'put':
            response = requests.put(url, json=payload, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
    else:
        if method != 'post':
            raise RuntimeError(f'Unsupported DingTalk OAPI method: {method}')
        response = requests.post(url, params={'access_token': access_token}, json=payload, timeout=10)
    response.raise_for_status()
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def _extract_task_id(payload):
    if not isinstance(payload, dict):
        return ''
    direct_keys = ['id', 'taskId', 'task_id']
    for key in direct_keys:
        value = payload.get(key)
        if value:
            return str(value)
    result = payload.get('result')
    if isinstance(result, dict):
        for key in direct_keys:
            value = result.get(key)
            if value:
                return str(value)
    return ''


def send_todo_task_result(user, title, content, url=None, source_id=None, originator=None):
    channel = _resolve_channel()
    if channel == models.ApprovalTask.TODO_CHANNEL_DISABLED:
        return TodoGatewayResult(ok=True, channel=channel, raw={'skipped': True})

    if channel == models.ApprovalTask.TODO_CHANNEL_OWN_OA:
        return _send_own_oa_task_result(
            originator=originator or user,
            assignee=user,
            process_code=_get_setting('OWN_OA_PROCESS_CODE'),
            title=title,
            content=content,
            url=url,
            source_id=source_id,
        )

    create_url_template = _get_setting('TODO_CREATE_URL')
    if not create_url_template:
        return TodoGatewayResult(ok=False, channel=channel, error='DingTalk todo create url not configured')

    user_id = getattr(user, 'dingtalk_user_id', None) or getattr(user, 'dingtalk_user', None)
    union_id = getattr(user, 'dingtalk_union_id', None) or getattr(user, 'dingtalk_union', None)
    operator_union_id = _get_setting('TODO_OPERATOR_UNION_ID') or union_id
    if not user_id and not union_id:
        return TodoGatewayResult(ok=False, channel=channel, error='User missing DingTalk identity')

    create_url = _format_url(
        create_url_template,
        user_id=user_id,
        union_id=union_id,
        operator_union_id=operator_union_id,
    )
    if _has_unresolved_placeholder(create_url):
        return TodoGatewayResult(
            ok=False,
            channel=channel,
            error='DingTalk todo create url contains unresolved placeholders',
        )
    task_url = url or ''
    is_openapi_create = dingtalk_client._is_openapi_url(create_url)
    payload = {
        'sourceId': source_id or f'approval-task-{user_id}-{title}',
        'subject': title,
        'description': content,
        'detailUrl': {
            'pcUrl': task_url,
            'appUrl': task_url,
        },
    }
    if is_openapi_create and union_id:
        payload['executorIds'] = [str(union_id)]
    if user_id and not _template_has_user_id(create_url_template) and not is_openapi_create:
        payload['executorId'] = str(user_id)

    try:
        raw = _send_request(create_url, payload)
        return TodoGatewayResult(ok=True, channel=channel, task_id=_extract_task_id(raw), raw=raw)
    except Exception as exc:
        return TodoGatewayResult(ok=False, channel=channel, error=str(exc))


def _send_own_oa_task_result(originator, assignee, process_code, title, content, url=None, source_id=None):
    channel = models.ApprovalTask.TODO_CHANNEL_OWN_OA
    create_url = _get_setting('OWN_OA_CREATE_URL') or DEFAULT_OWN_OA_CREATE_URL
    originator_id = getattr(originator, 'dingtalk_user_id', None)
    assignee_id = getattr(assignee, 'dingtalk_user_id', None)
    if not originator_id or not assignee_id:
        return TodoGatewayResult(ok=False, channel=channel, error='Missing DingTalk user id for own_oa task')

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
        raw = _send_request(create_url, payload)
        return TodoGatewayResult(ok=True, channel=channel, task_id=_extract_task_id(raw), raw=raw)
    except Exception as exc:
        return TodoGatewayResult(ok=False, channel=channel, error=str(exc))


def complete_todo_task_result(user, source_id=None, task_id=None, channel=''):
    resolved_channel = channel or _resolve_channel()
    if resolved_channel == models.ApprovalTask.TODO_CHANNEL_DISABLED:
        return TodoGatewayResult(ok=True, channel=resolved_channel, raw={'skipped': True})

    complete_url_template = _get_setting('TODO_COMPLETE_URL')
    if not complete_url_template:
        if resolved_channel == models.ApprovalTask.TODO_CHANNEL_OWN_OA:
            return TodoGatewayResult(ok=True, channel=resolved_channel, raw={'skipped': True})
        return TodoGatewayResult(ok=False, channel=resolved_channel, error='DingTalk todo complete url not configured')

    user_id = getattr(user, 'dingtalk_user_id', None) or getattr(user, 'dingtalk_user', None)
    union_id = getattr(user, 'dingtalk_union_id', None) or getattr(user, 'dingtalk_union', None)
    operator_union_id = _get_setting('TODO_OPERATOR_UNION_ID') or union_id
    if not user_id and not union_id:
        return TodoGatewayResult(ok=False, channel=resolved_channel, error='User missing DingTalk identity')

    resolved_task_id = task_id or ''
    if _template_has_task_id(complete_url_template) and not resolved_task_id:
        return TodoGatewayResult(
            ok=True,
            channel=resolved_channel,
            raw={'skipped': True, 'reason': 'missing_task_id'},
        )

    complete_url = _format_url(
        complete_url_template,
        user_id=user_id,
        union_id=union_id,
        operator_union_id=operator_union_id,
        task_id=resolved_task_id,
    )
    if _has_unresolved_placeholder(complete_url):
        return TodoGatewayResult(
            ok=False,
            channel=resolved_channel,
            error='DingTalk todo complete url contains unresolved placeholders',
        )
    if dingtalk_client._is_openapi_url(complete_url):
        payload = {'done': True}
        if union_id:
            payload['executorIds'] = [str(union_id)]
        request_method = 'put'
    else:
        payload = {'sourceId': source_id}
        request_method = 'post'
    if user_id and not _template_has_user_id(complete_url_template) and not dingtalk_client._is_openapi_url(complete_url):
        payload['executorId'] = str(user_id)

    try:
        raw = _send_request(complete_url, payload, method=request_method)
        return TodoGatewayResult(ok=True, channel=resolved_channel, task_id=resolved_task_id or _extract_task_id(raw), raw=raw)
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        if dingtalk_client._is_openapi_url(complete_url) and status_code == 404:
            return TodoGatewayResult(
                ok=True,
                channel=resolved_channel,
                task_id=resolved_task_id,
                raw={'skipped': True, 'reason': 'remote_task_not_found'},
            )
        return TodoGatewayResult(ok=False, channel=resolved_channel, error=str(exc))
    except Exception as exc:
        return TodoGatewayResult(ok=False, channel=resolved_channel, error=str(exc))


def send_todo_task(user, title, content, url=None, source_id=None, originator=None):
    result = send_todo_task_result(
        user=user,
        title=title,
        content=content,
        url=url,
        source_id=source_id,
        originator=originator,
    )
    return bool(result.ok)


def complete_todo_task(user, source_id=None, task_id=None):
    result = complete_todo_task_result(user=user, source_id=source_id, task_id=task_id)
    return bool(result.ok)


def _is_supported_target(task):
    return task.instance.target_type in {
        models.ApprovalFlow.TARGET_CONTRACT,
        models.ApprovalFlow.TARGET_INVOICE,
    }


def _build_default_content(task):
    return f'请审批 {task.instance.target_type} #{task.instance.object_id}'


def schedule_create_for_task(task, title='审批待办提醒', content='', url=None, originator=None):
    if not _is_supported_target(task):
        return
    if not content:
        content = _build_default_content(task)
    source_id = task.todo_source_id or build_todo_source_id(task.id)
    payload = {
        'title': title,
        'content': content,
        'url': url or build_task_url(task.id),
        'originator_id': getattr(originator, 'id', None),
    }
    transaction.on_commit(
        lambda: _enqueue_outbox(
            task_id=task.id,
            action=models.ApprovalTodoOutbox.ACTION_CREATE,
            source_id=source_id,
            payload=payload,
        )
    )


def schedule_complete_for_task(task, reason=''):
    if not _is_supported_target(task):
        return
    source_id = task.todo_source_id or build_todo_source_id(task.id)
    payload = {
        'reason': reason or '',
        'todo_task_id': task.todo_task_id,
    }
    transaction.on_commit(
        lambda: _enqueue_outbox(
            task_id=task.id,
            action=models.ApprovalTodoOutbox.ACTION_COMPLETE,
            source_id=source_id,
            payload=payload,
        )
    )


def _enqueue_outbox(task_id, action, source_id, payload):
    pending_statuses = [
        models.ApprovalTodoOutbox.STATUS_PENDING,
        models.ApprovalTodoOutbox.STATUS_FAILED,
        models.ApprovalTodoOutbox.STATUS_PROCESSING,
    ]
    exists = models.ApprovalTodoOutbox.objects.filter(
        task_id=task_id,
        action=action,
        source_id=source_id,
        status__in=pending_statuses,
    ).exists()
    if exists:
        return

    models.ApprovalTodoOutbox.objects.create(
        task_id=task_id,
        action=action,
        source_id=source_id,
        payload=payload or {},
        next_retry_at=timezone.now(),
    )
    models.ApprovalTask.objects.filter(id=task_id).update(
        todo_status=models.ApprovalTask.TODO_STATUS_QUEUED,
        todo_source_id=source_id,
        todo_next_retry_at=timezone.now(),
    )


def _next_retry_at(retry_count):
    if retry_count <= 0:
        retry_count = 1
    if retry_count > len(RETRY_DELAYS_SECONDS):
        return None
    delay_seconds = RETRY_DELAYS_SECONDS[retry_count - 1]
    return timezone.now() + timedelta(seconds=delay_seconds)


def process_outbox(batch_size=100):
    now = timezone.now()
    candidates = list(
        models.ApprovalTodoOutbox.objects
        .select_related('task', 'task__assignee', 'task__instance', 'task__instance__started_by')
        .filter(
            status__in=[models.ApprovalTodoOutbox.STATUS_PENDING, models.ApprovalTodoOutbox.STATUS_FAILED],
            next_retry_at__lte=now,
        )
        .order_by('id')[:batch_size]
    )

    summary = {'processed': 0, 'succeeded': 0, 'failed': 0, 'dead': 0}
    for item in candidates:
        result_status = _process_one(item)
        summary['processed'] += 1
        if result_status == models.ApprovalTodoOutbox.STATUS_SUCCEEDED:
            summary['succeeded'] += 1
        elif result_status == models.ApprovalTodoOutbox.STATUS_DEAD:
            summary['dead'] += 1
        else:
            summary['failed'] += 1
    return summary


def _process_one(item):
    item.status = models.ApprovalTodoOutbox.STATUS_PROCESSING
    item.save(update_fields=['status', 'updated_at'])

    task = item.task
    payload = item.payload or {}

    if item.action == models.ApprovalTodoOutbox.ACTION_CREATE:
        originator_id = payload.get('originator_id')
        originator = None
        if originator_id:
            originator = core_models.User.objects.filter(id=originator_id).first()
        originator = originator or task.instance.started_by
        result = send_todo_task_result(
            user=task.assignee,
            title=payload.get('title') or '审批待办提醒',
            content=payload.get('content') or _build_default_content(task),
            url=payload.get('url') or build_task_url(task.id),
            source_id=item.source_id or build_todo_source_id(task.id),
            originator=originator,
        )
    else:
        result = complete_todo_task_result(
            user=task.assignee,
            source_id=item.source_id or task.todo_source_id,
            task_id=task.todo_task_id or payload.get('todo_task_id') or '',
            channel=task.todo_channel,
        )

    if result.ok:
        _mark_success(item, task, result)
        return models.ApprovalTodoOutbox.STATUS_SUCCEEDED
    _mark_failure(item, task, result.error or 'Unknown todo error')
    return item.status


def _mark_success(item, task, result):
    now = timezone.now()
    if item.action == models.ApprovalTodoOutbox.ACTION_CREATE:
        task.todo_status = models.ApprovalTask.TODO_STATUS_CREATED
    else:
        task.todo_status = models.ApprovalTask.TODO_STATUS_COMPLETED
    task.todo_channel = result.channel or task.todo_channel or models.ApprovalTask.TODO_CHANNEL_UNKNOWN
    task.todo_source_id = item.source_id or task.todo_source_id or build_todo_source_id(task.id)
    if result.task_id:
        task.todo_task_id = result.task_id
    task.todo_last_error = ''
    task.todo_retry_count = 0
    task.todo_next_retry_at = None
    task.save(
        update_fields=[
            'todo_status', 'todo_channel', 'todo_source_id', 'todo_task_id',
            'todo_last_error', 'todo_retry_count', 'todo_next_retry_at', 'updated_at',
        ]
    )

    item.status = models.ApprovalTodoOutbox.STATUS_SUCCEEDED
    item.last_error = ''
    item.processed_at = now
    item.save(update_fields=['status', 'last_error', 'processed_at', 'updated_at'])

    models.ApprovalActionLog.objects.create(
        instance=task.instance,
        task=task,
        actor=task.assignee,
        action=(
            models.ApprovalActionLog.ACTION_TODO_CREATE
            if item.action == models.ApprovalTodoOutbox.ACTION_CREATE
            else models.ApprovalActionLog.ACTION_TODO_COMPLETE
        ),
        from_status='',
        to_status=task.todo_status,
        extra={
            'outbox_id': item.id,
            'channel': task.todo_channel,
            'source_id': task.todo_source_id,
            'task_id': task.todo_task_id,
        },
    )


def _mark_failure(item, task, error):
    retry_count = item.retry_count + 1
    retry_at = _next_retry_at(retry_count)
    if retry_at is None:
        item.status = models.ApprovalTodoOutbox.STATUS_DEAD
        next_retry_at = timezone.now()
    else:
        item.status = models.ApprovalTodoOutbox.STATUS_FAILED
        next_retry_at = retry_at
    item.retry_count = retry_count
    item.last_error = error[:2000]
    item.next_retry_at = next_retry_at
    item.save(update_fields=['status', 'retry_count', 'last_error', 'next_retry_at', 'updated_at'])

    task.todo_status = models.ApprovalTask.TODO_STATUS_FAILED
    task.todo_last_error = error[:2000]
    task.todo_retry_count = retry_count
    task.todo_next_retry_at = retry_at
    task.save(update_fields=['todo_status', 'todo_last_error', 'todo_retry_count', 'todo_next_retry_at', 'updated_at'])

    models.ApprovalActionLog.objects.create(
        instance=task.instance,
        task=task,
        actor=task.assignee,
        action=models.ApprovalActionLog.ACTION_TODO_FAILED,
        from_status='',
        to_status=task.todo_status,
        comment=error[:500],
        extra={
            'outbox_id': item.id,
            'outbox_action': item.action,
            'retry_count': retry_count,
            'next_retry_at': next_retry_at.isoformat() if next_retry_at else '',
            'is_dead': item.status == models.ApprovalTodoOutbox.STATUS_DEAD,
        },
    )
    logger.warning('Approval todo outbox failed: outbox=%s task=%s action=%s err=%s', item.id, task.id, item.action, error)

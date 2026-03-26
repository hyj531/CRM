import json
from pathlib import Path

from django.conf import settings

from core import models
from core.services import dingtalk_client


def _ensure_region(dept):
    dept_id = str(dept.get('id') or dept.get('dept_id') or '')
    if not dept_id:
        return None, False, False
    name = dept.get('name') or dept.get('title') or dept_id

    region, created = models.Region.objects.get_or_create(
        dingtalk_dept_id=dept_id,
        defaults={'name': name, 'code': f'dt-{dept_id}'},
    )
    updated = False
    if region.name != name:
        region.name = name
        updated = True
        region.save(update_fields=['name'])

    return region, created, updated


def _ensure_user(user, region):
    user_id = str(user.get('userid') or user.get('user_id') or '')
    if not user_id:
        return None, False, False

    username = user.get('username') or user.get('name') or user_id
    email = user.get('email') or ''
    mobile = user.get('mobile') or ''
    union_id = user.get('unionid') or user.get('union_id') or ''

    existing = models.User.objects.filter(dingtalk_user_id=user_id).first()
    if existing:
        updates = {}
        if existing.username != username:
            updates['username'] = username
        if email and existing.email != email:
            updates['email'] = email
        if mobile and existing.phone != mobile:
            updates['phone'] = mobile
        if union_id and existing.dingtalk_union_id != union_id:
            updates['dingtalk_union_id'] = union_id
        if region and existing.region_id != region.id:
            updates['region'] = region
        if updates:
            for key, value in updates.items():
                setattr(existing, key, value)
            existing.save(update_fields=list(updates.keys()))
            return existing, False, True
        return existing, False, False

    user_obj = models.User(
        username=username,
        email=email,
        dingtalk_user_id=user_id,
        dingtalk_union_id=union_id,
        phone=mobile,
        region=region,
        is_active=True,
    )
    user_obj.set_unusable_password()
    user_obj.save()
    return user_obj, True, False


def _load_sync_payload_from_file(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    departments = payload.get('departments') or []
    users_payload = payload.get('users') or []
    return departments, users_payload


def _resolve_sync_payload(departments=None, users_payload=None):
    sync_file = settings.DINGTALK.get('SYNC_FILE')
    loaded_from_file = False

    if departments is None and users_payload is None and sync_file:
        departments, users_payload = _load_sync_payload_from_file(sync_file)
        loaded_from_file = True

    if departments is None:
        departments = dingtalk_client.fetch_departments() or []

    if users_payload is None:
        if loaded_from_file:
            users_payload = []
        else:
            users_payload = []
            for dept in departments:
                dept_id = dept.get('id') or dept.get('dept_id')
                if dept_id is None:
                    continue
                users_payload.extend(dingtalk_client.fetch_department_users(dept_id) or [])

    return departments, users_payload


def sync_departments_and_users(departments=None, users_payload=None):
    departments, users_payload = _resolve_sync_payload(departments, users_payload)

    summary = {
        'departments_total': 0,
        'departments_created': 0,
        'departments_updated': 0,
        'departments_parent_updated': 0,
        'users_total': 0,
        'users_created': 0,
        'users_updated': 0,
    }

    region_by_dept_id = {}
    dept_parent_map = {}

    for dept in departments:
        summary['departments_total'] += 1
        dept_id = str(dept.get('id') or dept.get('dept_id') or '')
        if not dept_id:
            continue
        parent_id = dept.get('parent_id') or dept.get('parent') or None
        region, created, updated = _ensure_region(dept)
        if region:
            region_by_dept_id[dept_id] = region
            dept_parent_map[dept_id] = str(parent_id) if parent_id else ''
        if created:
            summary['departments_created'] += 1
        if updated:
            summary['departments_updated'] += 1

    for dept_id, parent_id in dept_parent_map.items():
        if not parent_id:
            continue
        region = region_by_dept_id.get(dept_id)
        parent = region_by_dept_id.get(parent_id)
        if region and parent and region.parent_id != parent.id:
            region.parent = parent
            region.save(update_fields=['parent'])
            summary['departments_parent_updated'] += 1

    for user in users_payload:
        summary['users_total'] += 1
        dept_id = user.get('dept_id') or user.get('department_id')
        region = None
        if dept_id:
            region = region_by_dept_id.get(str(dept_id))
            if region is None:
                region = models.Region.objects.filter(dingtalk_dept_id=str(dept_id)).first()
        _, created, updated = _ensure_user(user, region)
        if created:
            summary['users_created'] += 1
        if updated:
            summary['users_updated'] += 1

    return summary

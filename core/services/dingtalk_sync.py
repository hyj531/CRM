import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import models as django_models

from core import models
from core.services import dingtalk_client

ROOT_DEPT_ID = '1'


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
        # Keep existing region assignment to avoid overwriting manual adjustments.
        if existing.region_id is None and region is not None:
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


def _normalize_dept_id(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_user_dept_ids(user):
    ids = []
    for key in ('dept_id', 'department_id', 'deptId', 'departmentId'):
        value = user.get(key)
        if value is not None:
            ids.append(value)
    for key in ('dept_id_list', 'deptIdList', 'department_id_list', 'departmentIdList', 'dept_ids', 'deptIds'):
        value = user.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            ids.extend(value)
        elif isinstance(value, str):
            parts = [part.strip() for part in value.replace('[', '').replace(']', '').split(',') if part.strip()]
            if len(parts) > 1:
                ids.extend(parts)
            else:
                ids.append(value)
        else:
            ids.append(value)
    sync_dept_id = user.get('_sync_dept_id')
    if sync_dept_id is not None:
        ids.append(sync_dept_id)

    normalized = []
    seen = set()
    for item in ids:
        dept_id = _normalize_dept_id(item)
        if not dept_id or dept_id in seen:
            continue
        seen.add(dept_id)
        normalized.append(dept_id)
    return normalized


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
            dept_ids = dingtalk_client.fetch_department_ids() or []
            if not dept_ids:
                for dept in departments:
                    dept_id = dept.get('id') or dept.get('dept_id')
                    if dept_id is not None:
                        dept_ids.append(str(dept_id))

            for dept_id in dept_ids:
                users = dingtalk_client.fetch_department_users(dept_id) or []
                for user in users:
                    user_payload = dict(user)
                    user_payload['_sync_dept_id'] = dept_id
                    users_payload.append(user_payload)

    return departments, users_payload


def _select_sync_departments(departments):
    selected = []
    selected_ids = set()
    dept_parent_map = {}
    dept_by_id = {}

    for dept in departments:
        dept_id = _normalize_dept_id(dept.get('id') or dept.get('dept_id'))
        if not dept_id:
            continue
        parent_id = _normalize_dept_id(dept.get('parent_id') or dept.get('parent'))
        dept_parent_map[dept_id] = parent_id or ''
        dept_by_id[dept_id] = dept
        if dept_id == ROOT_DEPT_ID or parent_id == ROOT_DEPT_ID:
            selected_ids.add(dept_id)
            selected.append(dept)

    return selected, selected_ids, dept_parent_map, dept_by_id


def _resolve_top_level_dept_id(dept_id, dept_parent_map, region_by_dept_id):
    current = _normalize_dept_id(dept_id)
    visited = set()
    while current and current not in visited:
        visited.add(current)
        if current == ROOT_DEPT_ID:
            return None

        parent_id = _normalize_dept_id(dept_parent_map.get(current))
        if parent_id is None:
            region = region_by_dept_id.get(current)
            if region is None:
                region = models.Region.objects.filter(dingtalk_dept_id=current).select_related('parent').first()
                if region:
                    region_by_dept_id[current] = region
            if region:
                if region.parent and region.parent.dingtalk_dept_id:
                    parent_id = str(region.parent.dingtalk_dept_id)
                elif region.parent_id is None:
                    return current

        if parent_id == ROOT_DEPT_ID:
            return current
        current = parent_id
    return None


def _ensure_region_for_dept_id(dept_id, region_by_dept_id, dept_by_id):
    normalized = _normalize_dept_id(dept_id)
    if not normalized:
        return None
    region = region_by_dept_id.get(normalized)
    if region is not None:
        return region

    region = models.Region.objects.filter(dingtalk_dept_id=normalized).first()
    if region is not None:
        region_by_dept_id[normalized] = region
        return region

    dept = dept_by_id.get(normalized) or {'dept_id': normalized, 'name': f'dt-{normalized}'}
    region, _, _ = _ensure_region(dept)
    if region is not None:
        region_by_dept_id[normalized] = region
    return region


def _iter_region_fk_fields():
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, 'concrete', False):
                continue
            if isinstance(field, django_models.ForeignKey) and field.remote_field and field.remote_field.model == models.Region:
                yield model, field


def _cleanup_secondary_dingtalk_regions(selected_dept_ids, dept_parent_map, region_by_dept_id, dept_by_id):
    regions_to_remove = list(
        models.Region.objects.exclude(dingtalk_dept_id='').exclude(dingtalk_dept_id__in=selected_dept_ids)
    )
    if not regions_to_remove:
        return

    remap = {}
    for region in regions_to_remove:
        top_level_dept_id = _resolve_top_level_dept_id(region.dingtalk_dept_id, dept_parent_map, region_by_dept_id)
        if not top_level_dept_id:
            top_level_dept_id = ROOT_DEPT_ID
        target_region = _ensure_region_for_dept_id(top_level_dept_id, region_by_dept_id, dept_by_id)
        if target_region is None:
            continue
        remap[region.id] = target_region.id

    if remap:
        for model, field in _iter_region_fk_fields():
            field_id = f'{field.name}_id'
            for old_id, new_id in remap.items():
                if old_id == new_id:
                    continue
                model.objects.filter(**{field_id: old_id}).update(**{field_id: new_id})

    for region in regions_to_remove:
        region.delete()


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
    sync_departments, selected_dept_ids, dept_parent_map, dept_by_id = _select_sync_departments(departments)

    for dept in departments:
        summary['departments_total'] += 1

    for dept in sync_departments:
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

    _cleanup_secondary_dingtalk_regions(selected_dept_ids, dept_parent_map, region_by_dept_id, dept_by_id)

    user_entries = {}
    for user in users_payload:
        user_id = str(user.get('userid') or user.get('user_id') or '')
        if not user_id:
            continue
        dept_ids = _extract_user_dept_ids(user)
        top_level_region = None
        for dept_id in dept_ids:
            top_level_dept_id = _resolve_top_level_dept_id(dept_id, dept_parent_map, region_by_dept_id)
            if not top_level_dept_id:
                continue
            top_level_region = region_by_dept_id.get(top_level_dept_id)
            if top_level_region is None:
                top_level_region = models.Region.objects.filter(dingtalk_dept_id=top_level_dept_id).first()
                if top_level_region:
                    region_by_dept_id[top_level_dept_id] = top_level_region
            break

        existing = user_entries.get(user_id)
        if not existing:
            user_entries[user_id] = {
                'user': user,
                'region': top_level_region,
            }
        else:
            entry = existing
            if entry['region'] is None and top_level_region is not None:
                entry['region'] = top_level_region
            # Merge missing fields
            for field in ('username', 'name', 'email', 'mobile', 'unionid', 'union_id', 'dept_id', 'department_id'):
                if not entry['user'].get(field) and user.get(field):
                    entry['user'][field] = user.get(field)

    summary['users_total'] = len(user_entries)
    for entry in user_entries.values():
        _, created, updated = _ensure_user(entry['user'], entry['region'])
        if created:
            summary['users_created'] += 1
        if updated:
            summary['users_updated'] += 1

    return summary

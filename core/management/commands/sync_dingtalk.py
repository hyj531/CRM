import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import models
from core.services import dingtalk_client


def _ensure_region(dept):
    dept_id = str(dept.get('id') or dept.get('dept_id') or '')
    if not dept_id:
        return None
    name = dept.get('name') or dept.get('title') or dept_id
    parent_id = dept.get('parent_id') or dept.get('parent') or None

    region, created = models.Region.objects.get_or_create(
        dingtalk_dept_id=dept_id,
        defaults={'name': name, 'code': f'dt-{dept_id}'},
    )
    updates = {}
    if region.name != name:
        updates['name'] = name
    if updates:
        for key, value in updates.items():
            setattr(region, key, value)
        region.save(update_fields=list(updates.keys()))

    if parent_id:
        parent = models.Region.objects.filter(dingtalk_dept_id=str(parent_id)).first()
        if parent and region.parent_id != parent.id:
            region.parent = parent
            region.save(update_fields=['parent'])

    return region


def _ensure_user(user, region):
    user_id = str(user.get('userid') or user.get('user_id') or '')
    if not user_id:
        return None

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
        return existing

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
    return user_obj


class Command(BaseCommand):
    help = 'Sync DingTalk departments and users to Region/User'

    def handle(self, *args, **options):
        sync_file = settings.DINGTALK.get('SYNC_FILE')
        departments = None
        users_payload = None

        if sync_file:
            payload = json.loads(Path(sync_file).read_text(encoding='utf-8'))
            departments = payload.get('departments') or []
            users_payload = payload.get('users') or []
        else:
            departments = dingtalk_client.fetch_departments() or []

        if not departments:
            self.stdout.write(self.style.WARNING('No departments found.'))
        for dept in departments:
            _ensure_region(dept)

        if users_payload is None:
            users_payload = []
            for dept in departments:
                dept_id = dept.get('id') or dept.get('dept_id')
                if dept_id is None:
                    continue
                users_payload.extend(dingtalk_client.fetch_department_users(dept_id) or [])

        for user in users_payload:
            dept_id = user.get('dept_id') or user.get('department_id')
            region = None
            if dept_id:
                region = models.Region.objects.filter(dingtalk_dept_id=str(dept_id)).first()
            _ensure_user(user, region)

        self.stdout.write(self.style.SUCCESS('DingTalk sync complete.'))

from core import models


_SCOPE_PRIORITY = {
    models.Role.SCOPE_SELF: 0,
    models.Role.SCOPE_REGION: 1,
    models.Role.SCOPE_REGION_CHILDREN: 2,
    models.Role.SCOPE_ALL: 3,
}

_PERMISSION_FIELD_MAP = {
    'create': 'can_create',
    'update': 'can_update',
    'delete': 'can_delete',
    'approve': 'can_approve',
}


def get_user_role_ids(user):
    if user is None or getattr(user, 'is_anonymous', True):
        return []

    role_ids = list(user.roles.values_list('id', flat=True))
    if role_ids:
        return role_ids
    if user.role_id:
        return [user.role_id]
    return []


def get_effective_scope(user):
    if user is None or getattr(user, 'is_anonymous', True):
        return models.Role.SCOPE_REGION_CHILDREN
    if getattr(user, 'is_superuser', False):
        return models.Role.SCOPE_ALL

    role_ids = get_user_role_ids(user)
    if not role_ids:
        return models.Role.SCOPE_REGION_CHILDREN

    max_scope = models.Role.SCOPE_REGION_CHILDREN
    max_priority = _SCOPE_PRIORITY[max_scope]
    for scope in models.Role.objects.filter(id__in=role_ids).values_list('data_scope', flat=True):
        priority = _SCOPE_PRIORITY.get(scope, _SCOPE_PRIORITY[models.Role.SCOPE_REGION_CHILDREN])
        if priority > max_priority:
            max_scope = scope
            max_priority = priority
    return max_scope


def has_module_permission(user, module, permission_key):
    if user is None or getattr(user, 'is_anonymous', True):
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True

    field_name = _PERMISSION_FIELD_MAP.get(permission_key)
    if not field_name or not module:
        return False

    role_ids = get_user_role_ids(user)
    if not role_ids:
        return False

    return models.RolePermission.objects.filter(
        role_id__in=role_ids,
        module=module,
        **{field_name: True},
    ).exists()


def build_permissions_map(user):
    permissions_map = {}
    role_ids = get_user_role_ids(user)
    if not role_ids:
        return permissions_map

    for perm in models.RolePermission.objects.filter(role_id__in=role_ids):
        item = permissions_map.setdefault(
            perm.module,
            {'create': False, 'update': False, 'delete': False, 'approve': False},
        )
        item['create'] = item['create'] or bool(perm.can_create)
        item['update'] = item['update'] or bool(perm.can_update)
        item['delete'] = item['delete'] or bool(perm.can_delete)
        item['approve'] = item['approve'] or bool(perm.can_approve)
    return permissions_map


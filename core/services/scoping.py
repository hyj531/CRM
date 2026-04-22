from core import models
from core.services import role_access


def get_region_scope_ids(user):
    if user is None or user.is_anonymous:
        return []
    if user.is_superuser:
        return None

    scope = role_access.get_effective_scope(user)

    if scope == models.Role.SCOPE_ALL:
        return None

    if not user.region:
        return []

    if scope == models.Role.SCOPE_REGION:
        return [user.region_id]

    if scope == models.Role.SCOPE_REGION_CHILDREN:
        return [user.region_id] + user.region.get_descendant_ids()

    return [user.region_id]


def get_root_region_id(user):
    if user is None or getattr(user, 'is_anonymous', True):
        return None
    region = getattr(user, 'region', None)
    if not region:
        return None
    while region.parent_id:
        region = region.parent
    return region.id


def apply_scope(queryset, user, region_field='region', owner_field='owner'):
    if user is None or user.is_anonymous:
        return queryset.none()
    if user.is_superuser:
        return queryset

    scope = role_access.get_effective_scope(user)

    if scope == models.Role.SCOPE_ALL:
        return queryset

    if scope == models.Role.SCOPE_SELF:
        if not owner_field:
            return queryset.none()
        return queryset.filter(**{owner_field: user})

    region_ids = get_region_scope_ids(user)
    if region_ids is None:
        return queryset
    if not region_ids:
        return queryset.none()
    if not region_field:
        return queryset.none()
    return queryset.filter(**{f'{region_field}__in': region_ids})


def apply_account_scope(queryset, user):
    from django.db.models import Q

    base_queryset = apply_scope(queryset, user, region_field='region', owner_field='owner')

    if user is None or getattr(user, 'is_anonymous', True):
        return base_queryset
    if getattr(user, 'is_superuser', False):
        return base_queryset
    if role_access.get_effective_scope(user) == models.Role.SCOPE_ALL:
        return base_queryset

    root_region_id = get_root_region_id(user)
    if not root_region_id:
        return base_queryset

    return queryset.filter(
        Q(id__in=base_queryset.values('id')) | Q(region_id=root_region_id)
    )

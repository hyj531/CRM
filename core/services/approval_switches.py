from django.core.cache import cache
from django.db import IntegrityError

from core import models


APPROVAL_SWITCHES_CACHE_KEY = 'core:approval_switches:v1'
APPROVAL_SWITCHES_CACHE_TTL_SECONDS = 60
DEFAULT_SWITCHES = {'contract': True, 'invoice': True}


def _normalize_switches(setting):
    if not setting:
        return DEFAULT_SWITCHES.copy()
    return {
        'contract': bool(setting.contract_approval_enabled),
        'invoice': bool(setting.invoice_approval_enabled),
    }


def _load_singleton_setting():
    singleton_key = models.ApprovalModuleSetting.SINGLETON_KEY_DEFAULT
    try:
        setting, _ = models.ApprovalModuleSetting.objects.get_or_create(
            singleton_key=singleton_key,
            defaults={
                'contract_approval_enabled': True,
                'invoice_approval_enabled': True,
            },
        )
    except IntegrityError:
        setting = models.ApprovalModuleSetting.objects.get(singleton_key=singleton_key)
    return setting


def get_approval_switches(force_refresh=False):
    if not force_refresh:
        cached = cache.get(APPROVAL_SWITCHES_CACHE_KEY)
        if isinstance(cached, dict) and 'contract' in cached and 'invoice' in cached:
            return {
                'contract': bool(cached.get('contract')),
                'invoice': bool(cached.get('invoice')),
            }

    setting = _load_singleton_setting()
    switches = _normalize_switches(setting)
    cache.set(APPROVAL_SWITCHES_CACHE_KEY, switches, timeout=APPROVAL_SWITCHES_CACHE_TTL_SECONDS)
    return switches


def clear_approval_switches_cache():
    cache.delete(APPROVAL_SWITCHES_CACHE_KEY)


def is_contract_approval_enabled():
    return bool(get_approval_switches().get('contract', True))


def is_invoice_approval_enabled():
    return bool(get_approval_switches().get('invoice', True))

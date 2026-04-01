from typing import Dict

from approval.adapters.base import BaseApprovalAdapter


_registry: Dict[str, BaseApprovalAdapter] = {}


def register_adapter(adapter):
    instance = adapter() if isinstance(adapter, type) else adapter
    if not instance or not instance.get_target_type():
        raise ValueError('Adapter must have target_type')
    _registry[instance.get_target_type()] = instance
    return adapter


def get_adapter_for_type(target_type: str) -> BaseApprovalAdapter:
    return _registry.get(target_type)


def get_adapter_for_obj(obj) -> BaseApprovalAdapter:
    from approval.models import ApprovalFlow

    if obj is None:
        return None
    if hasattr(obj, '_meta'):
        model_name = obj.__class__.__name__.lower()
        if model_name == 'quote':
            return _registry.get(ApprovalFlow.TARGET_QUOTE)
        if model_name == 'contract':
            return _registry.get(ApprovalFlow.TARGET_CONTRACT)
        if model_name == 'invoice':
            return _registry.get(ApprovalFlow.TARGET_INVOICE)
    return None

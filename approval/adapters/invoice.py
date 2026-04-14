from approval.adapters.base import BaseApprovalAdapter
from approval.adapters.registry import register_adapter
from approval.models import ApprovalFlow
from core import models


@register_adapter
class InvoiceApprovalAdapter(BaseApprovalAdapter):
    target_type = ApprovalFlow.TARGET_INVOICE
    model = models.Invoice

    def get_display_fields(self, obj):
        account = obj.account
        account_name = account.full_name or account.short_name or getattr(account, 'name', '') if account else ''
        contract_name = ''
        if obj.contract:
            contract_name = obj.contract.name or obj.contract.contract_no or f'合同{obj.contract.id}'
        return [
            {'label': '开票编号', 'value': obj.invoice_no or f'开票{obj.id}'},
            {'label': '关联合同', 'value': contract_name},
            {'label': '客户', 'value': account_name},
            {'label': '开票金额', 'value': obj.amount},
            {'label': '开票日期', 'value': obj.issued_at or '-'},
            {'label': '负责人', 'value': obj.owner.username if obj.owner else ''},
            {'label': '区域', 'value': obj.region.name if obj.region else ''},
        ]

    def get_title(self, obj):
        return obj.invoice_no or f'开票{obj.id}'

    def set_approval_status(self, obj, status):
        status_map = {
            'pending': 'pending',
            'approved': 'approved',
            'rejected': 'rejected',
            'withdrawn': 'pending',
        }
        if hasattr(obj, 'approval_status'):
            obj.approval_status = status_map.get(status, 'pending')
            obj.save(update_fields=['approval_status'])
        return obj

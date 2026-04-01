from approval.adapters.base import BaseApprovalAdapter
from approval.adapters.registry import register_adapter
from approval.models import ApprovalFlow
from core import models


@register_adapter
class QuoteApprovalAdapter(BaseApprovalAdapter):
    target_type = ApprovalFlow.TARGET_QUOTE
    model = models.Quote

    def get_display_fields(self, obj):
        account = obj.account
        account_name = account.full_name or account.short_name or getattr(account, 'name', '') if account else ''
        return [
            {'label': '报价编号', 'value': f'报价{obj.id}'},
            {'label': '客户', 'value': account_name},
            {'label': '报价金额', 'value': obj.amount},
            {'label': '报价日期', 'value': obj.issued_at or '-'},
            {'label': '负责人', 'value': obj.owner.username if obj.owner else ''},
            {'label': '区域', 'value': obj.region.name if obj.region else ''},
        ]

    def get_title(self, obj):
        return f'报价{obj.id}'

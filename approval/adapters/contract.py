from approval.adapters.base import BaseApprovalAdapter
from approval.adapters.registry import register_adapter
from approval.models import ApprovalFlow
from core import models


@register_adapter
class ContractApprovalAdapter(BaseApprovalAdapter):
    target_type = ApprovalFlow.TARGET_CONTRACT
    model = models.Contract

    def get_display_fields(self, obj):
        account = obj.account
        account_name = account.full_name or account.short_name or getattr(account, 'name', '') or ''
        vendor_name = obj.vendor_company.name if obj.vendor_company else '-'
        return [
            {'label': '合同名称', 'value': obj.name or obj.contract_no or f'合同{obj.id}'},
            {'label': '客户', 'value': account_name},
            {'label': '乙方公司', 'value': vendor_name},
            {'label': '合同金额', 'value': obj.amount},
            {'label': '签署日期', 'value': obj.signed_at or '-'},
            {'label': '负责人', 'value': obj.owner.username if obj.owner else ''},
            {'label': '区域', 'value': obj.region.name if obj.region else ''},
            {'label': '备注', 'value': obj.remark or '-'},
        ]

    def get_title(self, obj):
        return obj.name or obj.contract_no or f'合同{obj.id}'

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

    def get_attachments(self, obj, request=None):
        attachments = []
        for item in obj.attachments.all().order_by('-created_at'):
            file_url = item.file.url if item.file else ''
            if request and file_url:
                file_url = request.build_absolute_uri(file_url)
            attachments.append({
                'id': item.id,
                'original_name': item.original_name or item.file.name.split('/')[-1] if item.file else '',
                'file_url': file_url,
                'owner_name': getattr(item.owner, 'username', '') if item.owner else '',
                'created_at': item.created_at,
            })
        return attachments

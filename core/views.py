from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
import csv
import json

from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

from core import models, serializers
from core.services import approval, scoping, dingtalk_client

User = get_user_model()


class TokenView(TokenObtainPairView):
    pass


class TokenRefreshView(TokenRefreshView):
    pass


class DingTalkSSOView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'detail': 'code is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = dingtalk_client.fetch_user_by_code(code)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not info.user_id:
            return Response({'detail': 'Invalid DingTalk user info'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(dingtalk_user_id=info.user_id).first()
        if not user:
            user = User(
                username=info.name or info.user_id,
                dingtalk_user_id=info.user_id,
                dingtalk_union_id=info.union_id or '',
                email=info.email or '',
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
        else:
            updates = {}
            if info.union_id and user.dingtalk_union_id != info.union_id:
                updates['dingtalk_union_id'] = info.union_id
            if info.email and user.email != info.email:
                updates['email'] = info.email
            if info.mobile and user.phone != info.mobile:
                updates['phone'] = info.mobile
            if updates:
                for key, value in updates.items():
                    setattr(user, key, value)
                user.save(update_fields=list(updates.keys()))

        refresh = RefreshToken.for_user(user)
        return Response({'refresh': str(refresh), 'access': str(refresh.access_token)})


class AdminManagePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class ReadOnlyOrStaffPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.is_staff


class DeleteRequiresStaffPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            user = request.user
            if not user or not user.is_authenticated:
                return False
            if user.is_staff or user.is_superuser:
                return True
            role = getattr(user, 'role', None)
            module = getattr(view, 'module_code', None)
            if not role or not module:
                return False
            perm = models.RolePermission.objects.filter(role=role, module=module).first()
            return bool(perm and perm.can_delete)
        return request.user and request.user.is_authenticated


class RegionScopedViewSet(viewsets.ModelViewSet):
    scope_region_field = 'region'
    scope_owner_field = 'owner'
    permission_classes = [DeleteRequiresStaffPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return scoping.apply_scope(
            queryset,
            self.request.user,
            region_field=self.scope_region_field,
            owner_field=self.scope_owner_field,
        )

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {}
        if 'owner' in serializer.fields and 'owner' not in serializer.validated_data:
            kwargs['owner'] = self.request.user
        if 'region' in serializer.fields and 'region' not in serializer.validated_data:
            region = self.request.user.region
            if region is None:
                region_field = serializer.Meta.model._meta.get_field('region')
                if not getattr(region_field, 'null', False):
                    raise ValidationError({'region': '请先为当前用户设置所属区域。'})
            kwargs['region'] = region
        serializer.save(**kwargs)

    @action(detail=False, methods=['get'])
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export.csv"'

        def normalize(value):
            if value is None:
                return ''
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        if data:
            fieldnames = list(data[0].keys())
        else:
            fieldnames = list(self.get_serializer().get_fields().keys())

        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow({key: normalize(row.get(key)) for key in fieldnames})
        return response


class RegionViewSet(viewsets.ModelViewSet):
    queryset = models.Region.objects.all()
    serializer_class = serializers.RegionSerializer
    permission_classes = [AdminManagePermission]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = models.Role.objects.all()
    serializer_class = serializers.RoleSerializer
    permission_classes = [AdminManagePermission]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [ReadOnlyOrStaffPermission]
    filterset_fields = ['region', 'role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user or user.is_anonymous:
            return queryset.none()
        if user.is_staff or user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        if not region_ids:
            return queryset.none()
        return queryset.filter(region_id__in=region_ids)


class LeadViewSet(RegionScopedViewSet):
    queryset = models.Lead.objects.all()
    serializer_class = serializers.LeadSerializer
    module_code = models.RolePermission.MODULE_LEAD
    filterset_fields = ['status', 'source', 'owner', 'region']
    search_fields = ['name', 'description']


class AccountViewSet(RegionScopedViewSet):
    queryset = models.Account.objects.all()
    serializer_class = serializers.AccountSerializer
    module_code = models.RolePermission.MODULE_ACCOUNT
    filterset_fields = ['status', 'customer_level', 'enterprise_nature', 'owner', 'region']
    search_fields = ['full_name', 'short_name', 'industry']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该客户已关联商机/合同/联系人，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)


class ContactViewSet(RegionScopedViewSet):
    queryset = models.Contact.objects.all()
    serializer_class = serializers.ContactSerializer
    module_code = models.RolePermission.MODULE_CONTACT
    filterset_fields = ['account', 'is_key_person', 'owner', 'region']
    search_fields = ['name', 'email', 'phone']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该联系人已被业务记录引用，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)


class LookupCategoryViewSet(viewsets.ModelViewSet):
    queryset = models.LookupCategory.objects.prefetch_related('options').all()
    serializer_class = serializers.LookupCategorySerializer
    permission_classes = [ReadOnlyOrStaffPermission]
    filterset_fields = ['code', 'is_active']
    search_fields = ['name', 'code']


class LookupOptionViewSet(viewsets.ModelViewSet):
    queryset = models.LookupOption.objects.select_related('category').all()
    serializer_class = serializers.LookupOptionSerializer
    permission_classes = [ReadOnlyOrStaffPermission]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code']


class OpportunityViewSet(RegionScopedViewSet):
    queryset = models.Opportunity.objects.all()
    serializer_class = serializers.OpportunitySerializer
    module_code = models.RolePermission.MODULE_OPPORTUNITY
    filterset_fields = [
        'stage', 'owner', 'region', 'account', 'contact',
        'opportunity_category', 'customer_level', 'lead_source',
    ]
    search_fields = ['opportunity_name']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该商机已关联合同/报价/活动/附件，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)


class OpportunityAttachmentViewSet(RegionScopedViewSet):
    queryset = models.OpportunityAttachment.objects.all()
    serializer_class = serializers.OpportunityAttachmentSerializer
    module_code = models.RolePermission.MODULE_OPPORTUNITY
    filterset_fields = ['opportunity', 'owner', 'region']
    search_fields = ['original_name', 'description']
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {}
        if 'owner' in serializer.fields and 'owner' not in serializer.validated_data:
            kwargs['owner'] = self.request.user

        region = self.request.user.region
        if 'region' in serializer.fields and 'region' not in serializer.validated_data:
            if region is None:
                opportunity = serializer.validated_data.get('opportunity')
                if opportunity and opportunity.region_id:
                    region = opportunity.region
            if region is None:
                raise ValidationError({'region': '请先为当前用户设置所属区域，或选择已归属区域的商机。'})
            kwargs['region'] = region

        attachment = serializer.save(**kwargs)
        if not attachment.original_name and attachment.file:
            attachment.original_name = attachment.file.name.split('/')[-1]
            attachment.save(update_fields=['original_name'])


class ActivityViewSet(RegionScopedViewSet):
    queryset = models.Activity.objects.all()
    serializer_class = serializers.ActivitySerializer
    module_code = models.RolePermission.MODULE_ACTIVITY
    filterset_fields = ['activity_type', 'owner', 'region', 'opportunity']
    search_fields = ['subject', 'description']

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from django.utils import timezone

        kwargs = {}
        if 'owner' in serializer.fields and 'owner' not in serializer.validated_data:
            kwargs['owner'] = self.request.user

        region = self.request.user.region
        if 'region' in serializer.fields and 'region' not in serializer.validated_data:
            if region is None:
                opportunity = serializer.validated_data.get('opportunity')
                account = serializer.validated_data.get('account')
                lead = serializer.validated_data.get('lead')
                for obj in (opportunity, account, lead):
                    if obj and obj.region_id:
                        region = obj.region
                        break
            if region is None:
                raise ValidationError({'region': '请先为当前用户设置所属区域，或选择已归属区域的商机。'})
            kwargs['region'] = region

        activity = serializer.save(**kwargs)

        opportunity = getattr(activity, 'opportunity', None)
        if opportunity:
            followup_time = activity.due_at or timezone.now()
            followup_note = activity.description or activity.subject
            opportunity.latest_followup_at = followup_time
            opportunity.latest_followup_note = followup_note
            opportunity.save(update_fields=['latest_followup_at', 'latest_followup_note'])


class TaskViewSet(RegionScopedViewSet):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer
    module_code = models.RolePermission.MODULE_TASK
    filterset_fields = ['status', 'owner', 'region']
    search_fields = ['subject']


class QuoteViewSet(RegionScopedViewSet):
    queryset = models.Quote.objects.all()
    serializer_class = serializers.QuoteSerializer
    module_code = models.RolePermission.MODULE_QUOTE
    filterset_fields = ['status', 'owner', 'region']

    @action(detail=True, methods=['post'])
    def submit_approval(self, request, pk=None):
        quote = self.get_object()
        instance = approval.start_approval(quote, request.user)
        return Response(serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class ContractViewSet(RegionScopedViewSet):
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    module_code = models.RolePermission.MODULE_CONTRACT
    filterset_fields = ['status', 'approval_status', 'account', 'opportunity', 'owner', 'region']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该合同已有关联开票或回款，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit_approval(self, request, pk=None):
        contract = self.get_object()
        instance = approval.start_approval(contract, request.user)
        return Response(serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class InvoiceViewSet(RegionScopedViewSet):
    queryset = models.Invoice.objects.all()
    serializer_class = serializers.InvoiceSerializer
    module_code = models.RolePermission.MODULE_INVOICE
    filterset_fields = ['status', 'approval_status', 'contract', 'account', 'owner', 'region']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该开票已有关联回款，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit_approval(self, request, pk=None):
        invoice = self.get_object()
        instance = approval.start_approval(invoice, request.user)
        return Response(serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(RegionScopedViewSet):
    queryset = models.Payment.objects.all()
    serializer_class = serializers.PaymentSerializer
    module_code = models.RolePermission.MODULE_PAYMENT
    filterset_fields = ['status', 'contract', 'invoice', 'owner', 'region']

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该回款已被关联，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)


class ApprovalFlowViewSet(RegionScopedViewSet):
    queryset = models.ApprovalFlow.objects.all()
    serializer_class = serializers.ApprovalFlowSerializer
    scope_owner_field = None

    def get_queryset(self):
        queryset = models.ApprovalFlow.objects.all()
        user = self.request.user
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        if not region_ids:
            return queryset.filter(region__isnull=True)
        return queryset.filter(Q(region_id__in=region_ids) | Q(region__isnull=True))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    user = request.user
    permissions_map = {}
    role = getattr(user, 'role', None)
    if role:
        for perm in models.RolePermission.objects.filter(role=role):
            permissions_map[perm.module] = {
                'create': perm.can_create,
                'update': perm.can_update,
                'delete': perm.can_delete,
                'approve': perm.can_approve,
            }
    return Response({
        'id': user.id,
        'username': user.username,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'region': user.region_id,
        'role': user.role_id,
        'permissions': permissions_map,
    })


class ApprovalStepViewSet(RegionScopedViewSet):
    queryset = models.ApprovalStep.objects.all()
    serializer_class = serializers.ApprovalStepSerializer
    scope_region_field = 'flow__region'
    scope_owner_field = None

    def get_queryset(self):
        queryset = models.ApprovalStep.objects.select_related('flow')
        user = self.request.user
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        if not region_ids:
            return queryset.filter(flow__region__isnull=True)
        return queryset.filter(Q(flow__region_id__in=region_ids) | Q(flow__region__isnull=True))


class ApprovalInstanceViewSet(RegionScopedViewSet):
    queryset = models.ApprovalInstance.objects.all()
    serializer_class = serializers.ApprovalInstanceSerializer
    scope_owner_field = 'started_by'

    def create(self, request, *args, **kwargs):
        target_type = request.data.get('target_type')
        object_id = request.data.get('object_id')
        if not target_type or not object_id:
            return Response({'detail': 'target_type and object_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        model_map = {
            models.ApprovalFlow.TARGET_QUOTE: models.Quote,
            models.ApprovalFlow.TARGET_CONTRACT: models.Contract,
            models.ApprovalFlow.TARGET_INVOICE: models.Invoice,
        }
        target_model = model_map.get(target_type)
        if not target_model:
            return Response({'detail': 'Unsupported target_type'}, status=status.HTTP_400_BAD_REQUEST)

        target_obj = scoping.apply_scope(target_model.objects.all(), request.user).filter(id=object_id).first()
        if not target_obj:
            return Response({'detail': 'Target not found'}, status=status.HTTP_404_NOT_FOUND)

        instance = approval.start_approval(target_obj, request.user)
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)


class ApprovalTaskViewSet(RegionScopedViewSet):
    queryset = models.ApprovalTask.objects.select_related('instance', 'step', 'assignee')
    serializer_class = serializers.ApprovalTaskSerializer
    scope_region_field = 'instance__region'
    scope_owner_field = 'assignee'

    @action(detail=True, methods=['post'])
    def decision(self, request, pk=None):
        task = self.get_object()
        approved = request.data.get('approved')
        comment = request.data.get('comment', '')
        if approved is None:
            return Response({'detail': 'approved is required'}, status=status.HTTP_400_BAD_REQUEST)
        approved_bool = str(approved).lower() in ['1', 'true', 'yes']
        try:
            instance = approval.approve_task(task, request.user, approved_bool, comment=comment)
        except (PermissionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ApprovalInstanceSerializer(instance).data)


class ReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        opportunity_stats = (
            scoping.apply_scope(models.Opportunity.objects.all(), request.user)
            .values('stage')
            .annotate(count=Count('id'), total_value=Sum('expected_amount'))
        )
        lead_stats = (
            scoping.apply_scope(models.Lead.objects.all(), request.user)
            .values('status')
            .annotate(count=Count('id'))
        )
        contract_total = (
            scoping.apply_scope(models.Contract.objects.all(), request.user)
            .aggregate(total_amount=Sum('amount'))
        )
        invoice_total = (
            scoping.apply_scope(models.Invoice.objects.all(), request.user)
            .aggregate(total_amount=Sum('amount'))
        )
        return Response({
            'opportunities': list(opportunity_stats),
            'leads': list(lead_stats),
            'contracts': contract_total,
            'invoices': invoice_total,
        })

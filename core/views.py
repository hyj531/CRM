from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
import csv
import json
import mimetypes
import os
from urllib.parse import quote as urlquote

from django.http import FileResponse, HttpResponse
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

from core import models, serializers
from core.services import scoping, dingtalk_client, dingtalk_sync, followup
from approval import serializers as approval_serializers
from approval.services import engine as approval_engine

User = get_user_model()

DIRECTORY_PERMISSION_FIELD_MAP = {
    'view': 'can_view',
    'download': 'can_download',
    'upload': 'can_upload',
    'edit': 'can_edit',
    'delete': 'can_delete',
}


def _is_admin(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def _has_directory_permission(user, directory, permission_key):
    if _is_admin(user):
        return True
    if not user or not user.is_authenticated or not directory or not user.role_id:
        return False
    field_name = DIRECTORY_PERMISSION_FIELD_MAP.get(permission_key)
    if not field_name:
        return False
    return models.CommonDocDirectoryPermission.objects.filter(
        directory=directory,
        role_id=user.role_id,
        **{field_name: True}
    ).exists()


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


class DingTalkSyncView(APIView):
    permission_classes = [AdminManagePermission]

    def post(self, request):
        serializer = serializers.DingTalkSyncRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        summary = dingtalk_sync.sync_departments_and_users(
            departments=serializer.validated_data.get('departments'),
            users_payload=serializer.validated_data.get('users'),
        )
        return Response(serializers.DingTalkSyncResultSerializer(summary).data)


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
    permission_classes = [ReadOnlyOrStaffPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(is_active=True)


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
        queryset = queryset.exclude(Q(region__name='外部人员') | Q(region__code='外部人员'))
        if self.request.query_params.get('opportunity_owner') in ('1', 'true', 'True'):
            queryset = queryset.filter(opportunity_items__isnull=False).distinct()
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

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {'created_by': self.request.user, 'updated_by': self.request.user}
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

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

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

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {'created_by': self.request.user, 'updated_by': self.request.user}
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

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

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

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from decimal import Decimal
        from django.db.models import DecimalField, Sum, Value, Count
        from django.db.models.functions import Coalesce

        queryset = scoping.apply_scope(models.Opportunity.objects.all(), request.user)

        totals = queryset.aggregate(
            total_count=Count('id'),
            total_amount=Coalesce(
                Sum('expected_amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        stage_stats = queryset.values('stage').annotate(count=Count('id'))
        stage_counts = {item['stage']: item['count'] for item in stage_stats}

        won_count = stage_counts.get(models.Opportunity.STAGE_WON, 0) + stage_counts.get(models.Opportunity.STAGE_FRAMEWORK, 0)
        lost_count = stage_counts.get(models.Opportunity.STAGE_LOST, 0)

        return Response({
            'total_count': totals.get('total_count') or 0,
            'total_amount': totals.get('total_amount') or Decimal('0'),
            'won_count': won_count,
            'lost_count': lost_count,
            'stage_counts': stage_counts,
        })

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {'created_by': self.request.user, 'updated_by': self.request.user}
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

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

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

        kwargs['created_by'] = self.request.user
        kwargs['updated_by'] = self.request.user
        activity = serializer.save(**kwargs)
        opportunity = getattr(activity, 'opportunity', None)
        if opportunity:
            followup.update_opportunity_latest_followup(opportunity.id)

    def perform_update(self, serializer):
        activity = serializer.save(updated_by=self.request.user)
        opportunity = getattr(activity, 'opportunity', None)
        if opportunity:
            followup.update_opportunity_latest_followup(opportunity.id)

    def perform_destroy(self, instance):
        opportunity_id = instance.opportunity_id
        instance.delete()
        if opportunity_id:
            followup.update_opportunity_latest_followup(opportunity_id)


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
        instance = approval_engine.start_approval(quote, request.user)
        return Response(approval_serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class ContractViewSet(RegionScopedViewSet):
    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    module_code = models.RolePermission.MODULE_CONTRACT
    filterset_fields = [
        'status', 'approval_status', 'account', 'opportunity', 'vendor_company',
        'owner', 'region', 'is_framework', 'framework_contract'
    ]
    search_fields = ['contract_no', 'name', 'account__full_name', 'account__short_name']
    ordering_fields = [
        'created_at', 'signed_at', 'amount',
        'account__full_name', 'account__short_name'
    ]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {'created_by': self.request.user, 'updated_by': self.request.user}
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

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        start = self.request.query_params.get('signed_at_start')
        end = self.request.query_params.get('signed_at_end')
        if start:
            queryset = queryset.filter(signed_at__gte=start)
        if end:
            queryset = queryset.filter(signed_at__lte=end)
        receivable_only = self.request.query_params.get('receivable_only')
        receivable_urgent = self.request.query_params.get('receivable_urgent')
        if receivable_only in ('1', 'true', 'True') or receivable_urgent in ('1', 'true', 'True', '0', 'false', 'False'):
            from django.db.models import DecimalField, ExpressionWrapper, F, Value
            from django.db.models.functions import Coalesce

            base_amount = Coalesce('current_output', 'amount')
            receivable_amount = ExpressionWrapper(
                base_amount - Coalesce(F('paid_total'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
            queryset = queryset.annotate(receivable_amount=receivable_amount)
            if receivable_only in ('1', 'true', 'True'):
                queryset = queryset.filter(receivable_amount__gt=0)
            if receivable_urgent in ('1', 'true', 'True'):
                queryset = queryset.filter(receivable_urgent=True)
            elif receivable_urgent in ('0', 'false', 'False'):
                queryset = queryset.filter(receivable_urgent=False)
        return queryset

    def get_queryset(self):
        from django.db.models import DecimalField, Sum, Value
        from django.db.models import OuterRef, Subquery
        from django.db.models.functions import Coalesce

        queryset = super().get_queryset()
        paid_subquery = models.Payment.objects.filter(contract_id=OuterRef('pk')) \
            .values('contract_id') \
            .annotate(total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )) \
            .values('total')[:1]

        return queryset.annotate(
            paid_total=Coalesce(
                Subquery(paid_subquery, output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from decimal import Decimal
        from django.http import QueryDict
        from django.db.models import DecimalField, Sum, Value
        from django.db.models.functions import Coalesce

        queryset = self.filter_queryset(self.get_queryset())
        paid_at_start = request.query_params.get('paid_at_start')
        paid_at_end = request.query_params.get('paid_at_end')
        region_param = request.query_params.get('region')
        signed_at_start = request.query_params.get('signed_at_start')
        signed_at_end = request.query_params.get('signed_at_end')

        totals = queryset.aggregate(
            contract_total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        )

        paid_query = models.Payment.objects.filter(contract_id__in=queryset.values('id'))
        if paid_at_start:
            paid_query = paid_query.filter(paid_at__gte=paid_at_start)
        if paid_at_end:
            paid_query = paid_query.filter(paid_at__lte=paid_at_end)

        paid_totals = {
            item['contract_id']: item['total']
            for item in paid_query.values('contract_id')
            .annotate(total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ))
        }

        paid_total_sum = sum(paid_totals.values(), Decimal('0'))
        receivable_total = Decimal('0')
        for item in queryset.values('id', 'amount', 'current_output'):
            base = item['current_output'] if item['current_output'] is not None else item['amount']
            if base is None:
                continue
            receivable_total += base - (paid_totals.get(item['id']) or Decimal('0'))

        # Paid total should ignore contract region filter and only apply signed_at when provided.
        original_get = request._request.GET
        try:
            query_copy = QueryDict(mutable=True)
            query_copy.update(original_get)
            if 'region' in query_copy:
                query_copy.pop('region')
            if not signed_at_start and 'signed_at_start' in query_copy:
                query_copy.pop('signed_at_start')
            if not signed_at_end and 'signed_at_end' in query_copy:
                query_copy.pop('signed_at_end')
            request._request.GET = query_copy
            paid_contract_queryset = self.filter_queryset(self.get_queryset())
        finally:
            request._request.GET = original_get

        paid_total_query = models.Payment.objects.filter(contract_id__in=paid_contract_queryset.values('id'))
        if paid_at_start:
            paid_total_query = paid_total_query.filter(paid_at__gte=paid_at_start)
        if paid_at_end:
            paid_total_query = paid_total_query.filter(paid_at__lte=paid_at_end)
        if region_param:
            paid_total_query = paid_total_query.filter(region=region_param)

        paid_total_sum_scoped = paid_total_query.aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).get('total') or Decimal('0')

        return Response({
            'contract_total': totals.get('contract_total') or 0,
            'paid_total': paid_total_sum_scoped,
            'receivable_total': receivable_total
        })

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        contract = self.get_object()
        # 先清理回款与附件，避免因外键保护导致无法删除合同
        contract.payments.all().delete()
        contract.attachments.all().delete()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该合同已关联合同开票，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit_approval(self, request, pk=None):
        contract = self.get_object()
        instance = approval_engine.start_approval(contract, request.user)
        return Response(approval_serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class ContractAttachmentViewSet(RegionScopedViewSet):
    queryset = models.ContractAttachment.objects.all()
    serializer_class = serializers.ContractAttachmentSerializer
    module_code = models.RolePermission.MODULE_CONTRACT
    filterset_fields = ['contract', 'owner', 'region']
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
                contract = serializer.validated_data.get('contract')
                if contract and contract.region_id:
                    region = contract.region
            if region is None:
                raise ValidationError({'region': '请先为当前用户设置所属区域，或选择已归属区域的合同。'})
            kwargs['region'] = region

        attachment = serializer.save(**kwargs)
        if not attachment.original_name and attachment.file:
            attachment.original_name = attachment.file.name.split('/')[-1]
            attachment.save(update_fields=['original_name'])


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
        instance = approval_engine.start_approval(invoice, request.user)
        return Response(approval_serializers.ApprovalInstanceSerializer(instance).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(RegionScopedViewSet):
    queryset = models.Payment.objects.all()
    serializer_class = serializers.PaymentSerializer
    module_code = models.RolePermission.MODULE_PAYMENT
    filterset_fields = ['status', 'contract', 'invoice', 'owner', 'region']

    def list(self, request, *args, **kwargs):
        from django.db.models import DecimalField, Sum, Value
        from django.db.models.functions import Coalesce

        queryset = self.filter_queryset(self.get_queryset())
        total_amount = queryset.aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ).get('total') or 0

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['total_amount'] = total_amount
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'total_amount': total_amount
        })

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        start = self.request.query_params.get('paid_at_start')
        end = self.request.query_params.get('paid_at_end')
        if start:
            queryset = queryset.filter(paid_at__gte=start)
        if end:
            queryset = queryset.filter(paid_at__lte=end)
        return queryset

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        kwargs = {'created_by': self.request.user}
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

    def perform_update(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': '该回款已被关联，无法删除。'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import DecimalField, Sum, Value, Count
        from django.db.models.functions import Coalesce

        queryset = self.filter_queryset(self.get_queryset())
        totals = queryset.aggregate(
            total_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            total_count=Count('id')
        )
        return Response({
            'total_amount': totals.get('total_amount') or 0,
            'total_count': totals.get('total_count') or 0
        })


class CommonDocDirectoryViewSet(viewsets.ModelViewSet):
    queryset = models.CommonDocDirectory.objects.all()
    serializer_class = serializers.CommonDocDirectorySerializer
    permission_classes = [permissions.IsAuthenticated]
    module_code = models.RolePermission.MODULE_COMMON_DOC
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['sort_order', 'id', 'created_at', 'updated_at', 'name']

    def _ensure_admin(self):
        if not _is_admin(self.request.user):
            raise PermissionDenied('仅管理员可维护目录。')

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if _is_admin(user):
            return queryset
        if not user.role_id:
            return queryset.none()
        allowed_directory_ids = models.CommonDocDirectoryPermission.objects.filter(
            role_id=user.role_id,
            can_view=True
        ).values('directory_id')
        return queryset.filter(id__in=allowed_directory_ids)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        if not _is_admin(user) and user and user.is_authenticated and user.role_id:
            permissions_qs = models.CommonDocDirectoryPermission.objects.filter(role_id=user.role_id)
            context['directory_permission_map'] = {
                perm.directory_id: perm for perm in permissions_qs
            }
        return context

    def perform_create(self, serializer):
        self._ensure_admin()
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        self._ensure_admin()
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        self._ensure_admin()
        instance = self.get_object()
        if instance.documents.exists():
            raise ValidationError({'detail': '该目录下仍有文档，请先清空后再删除。'})
        return super().destroy(request, *args, **kwargs)

    def _permissions_payload(self, directory):
        role_map = {
            item['id']: item
            for item in models.Role.objects.values('id', 'name').order_by('id')
        }
        permission_map = {
            item['role_id']: item
            for item in models.CommonDocDirectoryPermission.objects.filter(directory=directory).values(
                'role_id', 'can_view', 'can_download', 'can_upload', 'can_edit', 'can_delete'
            )
        }
        items = []
        for role_id, role in role_map.items():
            perm = permission_map.get(role_id, {})
            items.append({
                'role': role_id,
                'role_name': role['name'],
                'can_view': bool(perm.get('can_view')),
                'can_download': bool(perm.get('can_download')),
                'can_upload': bool(perm.get('can_upload')),
                'can_edit': bool(perm.get('can_edit')),
                'can_delete': bool(perm.get('can_delete')),
            })
        return {'directory': directory.id, 'items': items}

    @action(detail=True, methods=['get', 'put'])
    def permissions(self, request, pk=None):
        self._ensure_admin()
        directory = self.get_object()

        if request.method.lower() == 'get':
            return Response(self._permissions_payload(directory))

        items = request.data.get('items')
        if not isinstance(items, list):
            raise ValidationError({'items': '权限数据格式错误，应为数组。'})

        valid_role_ids = set(models.Role.objects.values_list('id', flat=True))
        target_map = {}
        for item in items:
            role_id = item.get('role')
            if role_id is None:
                continue
            try:
                role_id = int(role_id)
            except (TypeError, ValueError):
                raise ValidationError({'items': '角色ID格式错误。'})
            if role_id not in valid_role_ids:
                raise ValidationError({'items': f'角色不存在: {role_id}'})
            target_map[role_id] = {
                'can_view': _parse_bool(item.get('can_view')),
                'can_download': _parse_bool(item.get('can_download')),
                'can_upload': _parse_bool(item.get('can_upload')),
                'can_edit': _parse_bool(item.get('can_edit')),
                'can_delete': _parse_bool(item.get('can_delete')),
            }

        existing_qs = models.CommonDocDirectoryPermission.objects.filter(directory=directory)
        existing_map = {perm.role_id: perm for perm in existing_qs}
        processed_role_ids = set()

        for role_id, perms in target_map.items():
            processed_role_ids.add(role_id)
            if any(perms.values()):
                models.CommonDocDirectoryPermission.objects.update_or_create(
                    directory=directory,
                    role_id=role_id,
                    defaults=perms
                )
            else:
                models.CommonDocDirectoryPermission.objects.filter(
                    directory=directory,
                    role_id=role_id
                ).delete()

        stale_role_ids = [rid for rid in existing_map.keys() if rid not in processed_role_ids]
        if stale_role_ids:
            models.CommonDocDirectoryPermission.objects.filter(
                directory=directory,
                role_id__in=stale_role_ids
            ).delete()

        return Response(self._permissions_payload(directory))


class CommonDocumentViewSet(viewsets.ModelViewSet):
    queryset = models.CommonDocument.objects.select_related('directory', 'created_by', 'updated_by')
    serializer_class = serializers.CommonDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    module_code = models.RolePermission.MODULE_COMMON_DOC
    filterset_fields = ['directory']
    search_fields = ['title', 'original_name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'title']
    parser_classes = [MultiPartParser, FormParser]
    PREVIEW_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'}
    PREVIEW_TEXT_CONTENT_TYPES = {
        'txt': 'text/plain; charset=utf-8',
        'md': 'text/markdown; charset=utf-8',
        'log': 'text/plain; charset=utf-8',
        'csv': 'text/csv; charset=utf-8',
        'json': 'application/json; charset=utf-8',
        'xml': 'application/xml; charset=utf-8',
        'yaml': 'text/yaml; charset=utf-8',
        'yml': 'text/yaml; charset=utf-8',
        'html': 'text/html; charset=utf-8',
        'htm': 'text/html; charset=utf-8',
    }
    PREVIEW_TEXT_MAX_BYTES = 1024 * 1024

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if _is_admin(user):
            return queryset
        if not user.role_id:
            return queryset.none()
        allowed_directory_ids = models.CommonDocDirectoryPermission.objects.filter(
            role_id=user.role_id,
            can_view=True
        ).values('directory_id')
        return queryset.filter(directory_id__in=allowed_directory_ids)

    def perform_create(self, serializer):
        directory = serializer.validated_data.get('directory')
        if not _has_directory_permission(self.request.user, directory, 'upload'):
            raise PermissionDenied('当前目录无上传权限。')
        document = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        if document.file:
            document.original_name = os.path.basename(document.file.name)
            if not document.title:
                document.title = document.original_name
            document.save(update_fields=['original_name', 'title'])

    def perform_update(self, serializer):
        document = serializer.instance
        if not _has_directory_permission(self.request.user, document.directory, 'edit'):
            raise PermissionDenied('当前目录无编辑权限。')
        if 'directory' in serializer.validated_data and serializer.validated_data.get('directory') != document.directory:
            raise ValidationError({'directory': '暂不支持修改所属目录。'})
        updated_document = serializer.save(updated_by=self.request.user)
        if 'file' in serializer.validated_data and updated_document.file:
            updated_document.original_name = os.path.basename(updated_document.file.name)
            if not updated_document.title:
                updated_document.title = updated_document.original_name
            updated_document.save(update_fields=['original_name', 'title'])

    def perform_destroy(self, instance):
        if not _has_directory_permission(self.request.user, instance.directory, 'delete'):
            raise PermissionDenied('当前目录无删除权限。')
        instance.delete()

    def _preview_info(self, filename):
        ext = os.path.splitext((filename or '').lower())[1].lstrip('.')
        if ext in self.PREVIEW_IMAGE_EXTENSIONS:
            mime_type, _ = mimetypes.guess_type(filename)
            return ext, mime_type or 'image/jpeg', False
        if ext == 'pdf':
            return ext, 'application/pdf', False
        if ext in self.PREVIEW_TEXT_CONTENT_TYPES:
            return ext, self.PREVIEW_TEXT_CONTENT_TYPES[ext], True
        return ext, '', False

    def _inline_disposition(self, filename):
        safe_name = (filename or 'preview').replace('"', '')
        return f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{urlquote(filename or 'preview')}"

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document = models.CommonDocument.objects.select_related('directory').filter(pk=pk).first()
        if not document:
            return Response({'detail': '文档不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if not _has_directory_permission(request.user, document.directory, 'download'):
            raise PermissionDenied('当前目录无下载权限。')
        filename = document.original_name or os.path.basename(document.file.name)
        try:
            response = FileResponse(document.file.open('rb'), as_attachment=True, filename=filename)
        except FileNotFoundError:
            return Response({'detail': '文档文件不存在或已丢失。'}, status=status.HTTP_404_NOT_FOUND)
        return response

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        document = models.CommonDocument.objects.select_related('directory').filter(pk=pk).first()
        if not document:
            return Response({'detail': '文档不存在。'}, status=status.HTTP_404_NOT_FOUND)
        if not _has_directory_permission(request.user, document.directory, 'view'):
            raise PermissionDenied('当前目录无查看权限。')

        filename = document.original_name or os.path.basename(document.file.name)
        _, content_type, is_text = self._preview_info(filename)
        if not content_type:
            return Response(
                {'detail': '该文件类型暂不支持在线预览，请下载查看。'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if is_text and document.file.size > self.PREVIEW_TEXT_MAX_BYTES:
            return Response(
                {'detail': '文本文件过大，暂不支持在线预览，请下载查看。'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = FileResponse(
                document.file.open('rb'),
                as_attachment=False,
                filename=filename,
                content_type=content_type
            )
        except FileNotFoundError:
            return Response({'detail': '文档文件不存在或已丢失。'}, status=status.HTTP_404_NOT_FOUND)

        response['Content-Disposition'] = self._inline_disposition(filename)
        return response


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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password', '')
    new_password = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not new_password:
        return Response({'detail': '新密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
    if confirm_password and new_password != confirm_password:
        return Response({'detail': '两次输入的新密码不一致'}, status=status.HTTP_400_BAD_REQUEST)
    if user.has_usable_password():
        if not old_password:
            return Response({'detail': '请输入当前密码'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({'detail': '当前密码不正确'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        return Response(
            {'detail': exc.messages[0] if exc.messages else '密码不符合要求', 'errors': exc.messages},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(new_password)
    user.save(update_fields=['password'])
    return Response({'detail': '密码已更新'})


class ReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        from decimal import Decimal
        from django.db.models import DecimalField, Value, F, ExpressionWrapper
        from django.db.models.functions import Coalesce

        year_param = request.query_params.get('year')
        month_param = request.query_params.get('month')
        region_param = request.query_params.get('region')
        owner_param = request.query_params.get('owner')
        try:
            year = int(year_param) if year_param else None
        except (TypeError, ValueError):
            year = None
        try:
            month = int(month_param) if month_param else None
        except (TypeError, ValueError):
            month = None
        if month not in range(1, 13):
            month = None

        def apply_filters(queryset, date_field=None):
            if region_param:
                queryset = queryset.filter(region_id=region_param)
            if owner_param:
                queryset = queryset.filter(owner_id=owner_param)
            if year and date_field:
                queryset = queryset.filter(**{f'{date_field}__year': year})
                if month:
                    queryset = queryset.filter(**{f'{date_field}__month': month})
            return queryset

        opportunity_qs = scoping.apply_scope(models.Opportunity.objects.all(), request.user)
        lead_qs = scoping.apply_scope(models.Lead.objects.all(), request.user)
        contract_qs = scoping.apply_scope(models.Contract.objects.all(), request.user)
        invoice_qs = scoping.apply_scope(models.Invoice.objects.all(), request.user)
        payment_base_qs = scoping.apply_scope(models.Payment.objects.all(), request.user)

        opportunity_qs = apply_filters(opportunity_qs, date_field='created_at')
        lead_qs = apply_filters(lead_qs, date_field='created_at')
        contract_qs = apply_filters(contract_qs, date_field='signed_at')
        invoice_qs = apply_filters(invoice_qs, date_field='issued_at')
        payment_base_qs = apply_filters(payment_base_qs)
        payment_qs = apply_filters(payment_base_qs, date_field='paid_at')
        paid_payment_qs = payment_qs.filter(status__in=['partial', 'paid'])
        paid_payment_alltime_qs = payment_base_qs.filter(status__in=['partial', 'paid'])

        stage_stats_raw = opportunity_qs.values('stage').annotate(
            count=Count('id'),
            total_value=Coalesce(
                Sum('expected_amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        stage_map = {
            item['stage']: {
                'count': item['count'],
                'total_value': item['total_value'] or Decimal('0')
            }
            for item in stage_stats_raw
        }
        stage_list = []
        total_count = 0
        total_amount = Decimal('0')
        for stage_value, stage_label in models.Opportunity.STAGES:
            data = stage_map.get(stage_value, {'count': 0, 'total_value': Decimal('0')})
            total_count += data['count']
            total_amount += data['total_value'] or Decimal('0')
            stage_list.append({
                'stage': stage_value,
                'label': stage_label,
                'count': data['count'],
                'total_value': data['total_value'] or Decimal('0'),
            })

        from django.db.models.functions import Cast, Greatest, Least

        win_prob_decimal = Cast(
            Coalesce(F('win_probability'), Value(0)),
            output_field=DecimalField(max_digits=12, decimal_places=4)
        )
        # Clamp to 0-100% to avoid overflow and invalid data
        win_prob_clamped = Greatest(Least(win_prob_decimal, Value(100.0)), Value(0.0))
        percent_expr = ExpressionWrapper(
            win_prob_clamped / Value(100.0),
            output_field=DecimalField(max_digits=12, decimal_places=6)
        )
        weighted_expr = ExpressionWrapper(
            Coalesce(F('expected_amount'), Value(0)) * percent_expr,
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
        weighted_total = opportunity_qs.aggregate(
            weighted_total=Coalesce(
                Sum(weighted_expr),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).get('weighted_total') or Decimal('0')

        won_count = stage_map.get(models.Opportunity.STAGE_WON, {}).get('count', 0) + \
            stage_map.get(models.Opportunity.STAGE_FRAMEWORK, {}).get('count', 0)
        lost_count = stage_map.get(models.Opportunity.STAGE_LOST, {}).get('count', 0)

        lead_stats = lead_qs.values('status').annotate(count=Count('id'))

        contract_total = contract_qs.aggregate(
            total_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        invoice_total = invoice_qs.aggregate(
            total_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        payment_total = paid_payment_qs.aggregate(
            total_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        paid_totals = {
            item['contract_id']: item['total']
            for item in payment_base_qs.filter(contract_id__in=contract_qs.values('id'))
            .values('contract_id')
            .annotate(total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ))
        }
        receivable_total = Decimal('0')
        for item in contract_qs.values('id', 'amount', 'current_output'):
            base = item['current_output'] if item['current_output'] is not None else item['amount']
            if base is None:
                continue
            receivable_total += base - (paid_totals.get(item['id']) or Decimal('0'))

        owner_map = {}
        for item in opportunity_qs.values('owner_id', 'owner__username').annotate(
            opportunity_count=Count('id'),
            expected_amount=Coalesce(
                Sum('expected_amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            owner_map[item['owner_id']] = {
                'owner_id': item['owner_id'],
                'owner_name': item['owner__username'] or '',
                'opportunity_count': item['opportunity_count'],
                'expected_amount': item['expected_amount'] or Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            }

        for item in contract_qs.values('owner_id').annotate(
            contract_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            entry = owner_map.setdefault(item['owner_id'], {
                'owner_id': item['owner_id'],
                'owner_name': '',
                'opportunity_count': 0,
                'expected_amount': Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            })
            entry['contract_amount'] = item['contract_amount'] or Decimal('0')

        for item in paid_payment_qs.values('owner_id').annotate(
            payment_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            entry = owner_map.setdefault(item['owner_id'], {
                'owner_id': item['owner_id'],
                'owner_name': '',
                'opportunity_count': 0,
                'expected_amount': Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            })
            entry['payment_amount'] = item['payment_amount'] or Decimal('0')

        missing_owner_ids = [oid for oid, item in owner_map.items() if oid and not item.get('owner_name')]
        if missing_owner_ids:
            name_map = {
                item['id']: item['username']
                for item in User.objects.filter(id__in=missing_owner_ids).values('id', 'username')
            }
            for oid in missing_owner_ids:
                owner_map[oid]['owner_name'] = name_map.get(oid, f'ID {oid}')

        region_map = {}
        for item in opportunity_qs.values('region_id', 'region__name').annotate(
            opportunity_count=Count('id'),
            expected_amount=Coalesce(
                Sum('expected_amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            region_map[item['region_id']] = {
                'region_id': item['region_id'],
                'region_name': item['region__name'] or '',
                'opportunity_count': item['opportunity_count'],
                'expected_amount': item['expected_amount'] or Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            }

        for item in contract_qs.values('region_id').annotate(
            contract_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            entry = region_map.setdefault(item['region_id'], {
                'region_id': item['region_id'],
                'region_name': '',
                'opportunity_count': 0,
                'expected_amount': Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            })
            entry['contract_amount'] = item['contract_amount'] or Decimal('0')

        for item in paid_payment_qs.values('region_id').annotate(
            payment_amount=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ):
            entry = region_map.setdefault(item['region_id'], {
                'region_id': item['region_id'],
                'region_name': '',
                'opportunity_count': 0,
                'expected_amount': Decimal('0'),
                'contract_amount': Decimal('0'),
                'payment_amount': Decimal('0'),
            })
            entry['payment_amount'] = item['payment_amount'] or Decimal('0')

        missing_region_ids = [rid for rid, item in region_map.items() if rid and not item.get('region_name')]
        if missing_region_ids:
            name_map = {
                item['id']: item['name']
                for item in models.Region.objects.filter(id__in=missing_region_ids).values('id', 'name')
            }
            for rid in missing_region_ids:
                region_map[rid]['region_name'] = name_map.get(rid, f'ID {rid}')

        limit_param = request.query_params.get('limit')
        try:
            limit = max(1, min(int(limit_param), 50)) if limit_param else 10
        except (TypeError, ValueError):
            limit = 10

        owner_performance = sorted(
            owner_map.values(),
            key=lambda item: (item.get('contract_amount') or 0, item.get('expected_amount') or 0),
            reverse=True
        )[:limit]

        region_performance = sorted(
            region_map.values(),
            key=lambda item: (item.get('contract_amount') or 0, item.get('expected_amount') or 0),
            reverse=True
        )[:limit]

        return Response({
            'opportunities': list(stage_stats_raw),
            'opportunity_stages': stage_list,
            'opportunity_totals': {
                'count': total_count,
                'total_value': total_amount,
                'weighted_total': weighted_total,
                'won_count': won_count,
                'lost_count': lost_count,
            },
            'leads': list(lead_stats),
            'contracts': contract_total,
            'invoices': invoice_total,
            'payments': payment_total,
            'contract_summary': {
                'contract_total': contract_total.get('total_amount') or Decimal('0'),
                'paid_total': payment_total.get('total_amount') or Decimal('0'),
                'receivable_total': receivable_total,
            },
            'owner_performance': owner_performance,
            'region_performance': region_performance,
        })

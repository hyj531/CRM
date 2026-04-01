from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from approval import models, serializers
from approval.adapters import registry
from approval.services import engine
from core import models as core_models
from core.services import scoping


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
            perm = core_models.RolePermission.objects.filter(role=role, module=module).first()
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


class ApprovalStepViewSet(RegionScopedViewSet):
    queryset = models.ApprovalStep.objects.select_related('flow')
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

        adapter = registry.get_adapter_for_type(target_type)
        target_model = getattr(adapter, 'model', None) if adapter else None
        if not target_model:
            return Response({'detail': 'Unsupported target_type'}, status=status.HTTP_400_BAD_REQUEST)

        target_obj = scoping.apply_scope(target_model.objects.all(), request.user).filter(id=object_id).first()
        if not target_obj:
            return Response({'detail': 'Target not found'}, status=status.HTTP_404_NOT_FOUND)

        instance = engine.start_approval(target_obj, request.user)
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)


class ApprovalTaskViewSet(RegionScopedViewSet):
    queryset = models.ApprovalTask.objects.select_related('instance', 'step', 'assignee')
    serializer_class = serializers.ApprovalTaskSerializer
    scope_region_field = 'instance__region'
    scope_owner_field = 'assignee'
    filterset_fields = ['status', 'instance__target_type']
    ordering_fields = ['created_at', 'decided_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def decision(self, request, pk=None):
        task = self.get_object()
        approved = request.data.get('approved')
        comment = request.data.get('comment', '')
        if approved is None:
            return Response({'detail': 'approved is required'}, status=status.HTTP_400_BAD_REQUEST)
        approved_bool = str(approved).lower() in ['1', 'true', 'yes']
        try:
            instance = engine.approve_task(task, request.user, approved_bool, comment=comment)
        except (PermissionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ApprovalInstanceSerializer(instance).data)

    @action(detail=True, methods=['get'])
    def detail(self, request, pk=None):
        task = self.get_object()
        data = engine.get_task_detail(task, request=request)
        return Response(data)

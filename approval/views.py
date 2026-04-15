from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from approval import models, serializers
from approval.adapters import registry
from approval.services import engine
from core import models as core_models
from core.services import scoping, role_access


class DeleteRequiresStaffPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            user = request.user
            if not user or not user.is_authenticated:
                return False
            module = getattr(view, 'module_code', None)
            return role_access.has_module_permission(user, module, 'delete')
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
        queryset = models.ApprovalFlow.objects.prefetch_related('regions')
        user = self.request.user
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        if not region_ids:
            return queryset.filter(
                Q(scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
                | Q(region__isnull=True, regions__isnull=True)
            ).distinct()
        return queryset.filter(
            Q(region_id__in=region_ids)
            | Q(regions__id__in=region_ids)
            | Q(scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
        ).distinct()


class ApprovalStepViewSet(RegionScopedViewSet):
    queryset = models.ApprovalStep.objects.select_related('flow')
    serializer_class = serializers.ApprovalStepSerializer
    scope_region_field = 'flow__region'
    scope_owner_field = None

    def get_queryset(self):
        queryset = models.ApprovalStep.objects.select_related('flow').prefetch_related('flow__regions')
        user = self.request.user
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        if not region_ids:
            return queryset.filter(
                Q(flow__scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
                | Q(flow__region__isnull=True, flow__regions__isnull=True)
            ).distinct()
        return queryset.filter(
            Q(flow__region_id__in=region_ids)
            | Q(flow__regions__id__in=region_ids)
            | Q(flow__scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
        ).distinct()


class ApprovalFlowConfigPermission(permissions.BasePermission):
    message = '仅管理员可维护审批配置。'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class ApprovalFlowConfigViewSet(viewsets.ModelViewSet):
    queryset = models.ApprovalFlow.objects.prefetch_related('regions', 'steps')
    serializer_class = serializers.ApprovalFlowConfigSerializer
    permission_classes = [ApprovalFlowConfigPermission]
    ordering = ['-priority', '-updated_at', '-id']

    def get_queryset(self):
        queryset = self.queryset
        target_type = self.request.query_params.get('target_type')
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        is_active = self.request.query_params.get('is_active')
        if is_active in ('true', 'false'):
            queryset = queryset.filter(is_active=(is_active == 'true'))
        status_value = self.request.query_params.get('status')
        if status_value:
            queryset = queryset.filter(status=status_value)

        region_id = self.request.query_params.get('region_id')
        if region_id:
            queryset = queryset.filter(
                Q(scope_mode=models.ApprovalFlow.SCOPE_ALL_REGIONS)
                | Q(regions__id=region_id)
                | Q(region_id=region_id)
            ).distinct()
        return queryset.order_by(*self.ordering)

    def perform_destroy(self, instance):
        instance.steps.all().delete()
        super().perform_destroy(instance)

    def _flow_preview_regions(self, flow, explicit_region=None):
        if explicit_region is not None:
            return [explicit_region]
        if flow.scope_mode == models.ApprovalFlow.SCOPE_SELECTED_REGIONS:
            return list(flow.regions.filter(is_active=True).order_by('id'))
        return list(core_models.Region.objects.filter(is_active=True).order_by('id'))

    def _resolve_preview_users(self, step, region):
        if step.assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_USER:
            if step.approver_user and step.approver_user.is_active:
                return [step.approver_user]
            return []
        users_qs = core_models.User.objects.filter(
            Q(role=step.approver_role) | Q(roles=step.approver_role),
            is_active=True,
        ).distinct()
        if step.assignee_scope == models.ApprovalStep.ASSIGNEE_SCOPE_REGION:
            users_qs = users_qs.filter(region=region)
        return list(users_qs.order_by('id'))

    def _validate_publish_flow(self, flow):
        steps = list(flow.steps.select_related('approver_role', 'approver_user').order_by('order', 'id'))
        if not steps:
            raise ValueError('至少需要一个审批节点。')
        if flow.effective_from and flow.effective_to and flow.effective_from > flow.effective_to:
            raise ValueError('生效结束时间不能早于生效开始时间。')

        preview_regions = self._flow_preview_regions(flow)
        if flow.scope_mode == models.ApprovalFlow.SCOPE_SELECTED_REGIONS and not preview_regions:
            raise ValueError('指定区域范围必须至少选择一个区域。')

        for step in steps:
            if step.assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_ROLE and not step.approver_role_id:
                raise ValueError(f'节点“{step.name}”未配置审批角色。')
            if step.assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_USER and not step.approver_user_id:
                raise ValueError(f'节点“{step.name}”未配置审批人。')

        warnings = []
        for region in preview_regions:
            for step in steps:
                assignees = self._resolve_preview_users(step, region)
                if not assignees:
                    warnings.append({
                        'region_id': region.id,
                        'region_name': region.name,
                        'step_id': step.id,
                        'step_order': step.order,
                        'step_name': step.name or '',
                        'message': f'第{step.order}节点在区域“{region.name}”未匹配审批人，将自动跳过。',
                    })
        return warnings

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        flow = self.get_object()
        try:
            warnings = self._validate_publish_flow(flow)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            flow.status = models.ApprovalFlow.STATUS_PUBLISHED
            flow.is_active = True
            flow.save(update_fields=['status', 'is_active', 'updated_at'])

        data = self.get_serializer(flow).data
        data['warnings'] = warnings
        return Response(data)

    @action(detail=True, methods=['get'], url_path='preview-assignees')
    def preview_assignees(self, request, pk=None):
        flow = self.get_object()
        region_id = request.query_params.get('region_id')
        region = None
        if region_id:
            region = core_models.Region.objects.filter(id=region_id).first()
            if not region:
                return Response({'detail': '区域不存在。'}, status=status.HTTP_400_BAD_REQUEST)

        preview_regions = self._flow_preview_regions(flow, explicit_region=region)
        steps = list(flow.steps.select_related('approver_role', 'approver_user').order_by('order', 'id'))
        items = []
        for region_item in preview_regions:
            region_rows = []
            for step in steps:
                assignees = self._resolve_preview_users(step, region_item)
                region_rows.append({
                    'step_id': step.id,
                    'step_order': step.order,
                    'step_name': step.name,
                    'matched': [
                        {
                            'id': user.id,
                            'username': user.username,
                            'region': user.region_id,
                        }
                        for user in assignees
                    ],
                    'matched_count': len(assignees),
                    'will_auto_skip': len(assignees) == 0,
                })
            items.append({
                'region_id': region_item.id,
                'region_name': region_item.name,
                'steps': region_rows,
            })
        return Response({'items': items})


class ApprovalInstanceViewSet(RegionScopedViewSet):
    SLA_HOURS = 24
    SLA_WARNING_HOURS = 4

    queryset = models.ApprovalInstance.objects.select_related('started_by', 'region')
    serializer_class = serializers.ApprovalInstanceSerializer
    scope_owner_field = 'started_by'

    def get_queryset(self):
        return self._scoped_instances_queryset(self.request.user)

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

        try:
            instance = engine.start_approval(target_obj, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        instance = self.get_object()
        comment = request.data.get('comment', '')
        try:
            instance = engine.withdraw_approval(instance, request.user, comment=comment)
        except (PermissionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['get'], url_path='detail', url_name='detail')
    def instance_detail_action(self, request, pk=None):
        instance = self.get_object()
        data = engine.get_instance_detail(instance, request=request)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='mine')
    def mine(self, request):
        tab = request.query_params.get('tab', 'pending')
        if tab not in {'pending', 'processed', 'started'}:
            return Response({'detail': 'tab must be pending/processed/started'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        queryset = self._scoped_instances_queryset(user)

        if tab == 'pending':
            queryset = queryset.filter(
                tasks__assignee=user,
                tasks__status=models.ApprovalTask.STATUS_PENDING,
            )
        elif tab == 'processed':
            mine_handled_tasks = models.ApprovalTask.objects.filter(
                instance_id=OuterRef('pk'),
                assignee=user,
                status__in=[
                    models.ApprovalTask.STATUS_APPROVED,
                    models.ApprovalTask.STATUS_REJECTED,
                    models.ApprovalTask.STATUS_CANCELED,
                ],
            )
            mine_pending_tasks = models.ApprovalTask.objects.filter(
                instance_id=OuterRef('pk'),
                assignee=user,
                status=models.ApprovalTask.STATUS_PENDING,
            )
            queryset = queryset.annotate(
                _mine_handled=Exists(mine_handled_tasks),
                _mine_pending=Exists(mine_pending_tasks),
            ).filter(
                _mine_handled=True,
                _mine_pending=False,
            )
        else:
            queryset = queryset.filter(started_by=user)

        target_type = request.query_params.get('target_type')
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        region_id = request.query_params.get('region')
        if region_id:
            queryset = queryset.filter(region_id=region_id)

        instance_status = request.query_params.get('instance_status')
        if instance_status:
            queryset = queryset.filter(status=instance_status)

        started_by = request.query_params.get('started_by')
        if started_by:
            queryset = queryset.filter(started_by_id=started_by)

        created_from = self._parse_date(request.query_params.get('created_from'))
        if created_from:
            queryset = queryset.filter(created_at__gte=timezone.make_aware(datetime.combine(created_from, time.min)))

        created_to = self._parse_date(request.query_params.get('created_to'))
        if created_to:
            queryset = queryset.filter(created_at__lte=timezone.make_aware(datetime.combine(created_to, time.max)))

        task_queryset = models.ApprovalTask.objects.select_related('step', 'assignee').order_by('step__order', 'id')
        queryset = (
            queryset.distinct()
            .order_by('-created_at', '-id')
            .prefetch_related(Prefetch('tasks', queryset=task_queryset))
        )

        items = [self._build_mine_item(instance, user) for instance in queryset]
        keyword = (request.query_params.get('keyword') or '').strip().lower()
        if keyword:
            items = [item for item in items if self._match_keyword(item, keyword)]

        if tab == 'pending':
            items.sort(
                key=lambda item: (
                    0 if item['sla_level'] == 'overdue' else 1 if item['sla_level'] == 'warning' else 2,
                    -(self._dt_to_ts(item.get('created_at'))),
                )
            )
        else:
            items.sort(key=lambda item: -self._dt_to_ts(item.get('updated_at')))

        page = self.paginate_queryset(items)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(items)

    @action(detail=False, methods=['get'], url_path='mine/stats')
    def mine_stats(self, request):
        user = request.user
        queryset = self._scoped_instances_queryset(user)

        pending_qs = queryset.filter(
            tasks__assignee=user,
            tasks__status=models.ApprovalTask.STATUS_PENDING,
        ).distinct()
        pending_instances = pending_qs.prefetch_related(
            Prefetch(
                'tasks',
                queryset=models.ApprovalTask.objects.select_related('step', 'assignee').order_by('step__order', 'id')
            )
        )
        pending_items = [self._build_mine_item(instance, user) for instance in pending_instances]
        overdue_count = len([item for item in pending_items if item.get('sla_level') == 'overdue'])

        now = timezone.localtime()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        processed_today_count = models.ApprovalTask.objects.filter(
            assignee=user,
            status__in=[
                models.ApprovalTask.STATUS_APPROVED,
                models.ApprovalTask.STATUS_REJECTED,
                models.ApprovalTask.STATUS_CANCELED,
            ],
            decided_at__gte=day_start,
            decided_at__lte=day_end,
            instance__in=queryset,
        ).count()

        started_running_count = queryset.filter(
            started_by=user,
            status=models.ApprovalInstance.STATUS_PENDING,
        ).count()

        return Response({
            'pending_count': pending_qs.count(),
            'overdue_count': overdue_count,
            'processed_today_count': processed_today_count,
            'started_running_count': started_running_count,
        })

    def _build_mine_item(self, instance, user):
        target_obj = instance.content_object
        adapter = registry.get_adapter_for_type(instance.target_type)
        target_title = ''
        if adapter and target_obj:
            target_title = adapter.get_title(target_obj)
        if not target_title:
            target_title = f'{instance.target_type} #{instance.object_id}'

        tasks = list(instance.tasks.all())
        my_pending_tasks = [task for task in tasks if task.assignee_id == user.id and task.status == models.ApprovalTask.STATUS_PENDING]
        my_processed_tasks = [
            task
            for task in tasks
            if task.assignee_id == user.id
            and task.status in (
                models.ApprovalTask.STATUS_APPROVED,
                models.ApprovalTask.STATUS_REJECTED,
                models.ApprovalTask.STATUS_CANCELED,
            )
        ]
        my_processed_tasks.sort(
            key=lambda task: task.decided_at or task.updated_at or task.created_at,
            reverse=True,
        )
        my_last_task = my_processed_tasks[0] if my_processed_tasks else None

        current_step_name = ''
        for task in tasks:
            if task.step and task.step.order == instance.current_step:
                current_step_name = task.step.name or ''
                break

        current_approvers = []
        approver_seen_ids = set()
        for task in tasks:
            if task.status != models.ApprovalTask.STATUS_PENDING:
                continue
            if task.assignee_id in approver_seen_ids:
                continue
            approver_seen_ids.add(task.assignee_id)
            current_approvers.append({
                'id': task.assignee_id,
                'username': getattr(task.assignee, 'username', ''),
            })

        sla_deadline_at = None
        sla_remaining_seconds = None
        sla_level = 'normal'
        if instance.status == models.ApprovalInstance.STATUS_PENDING:
            deadline_at = instance.created_at + timedelta(hours=self.SLA_HOURS)
            sla_deadline_at = deadline_at
            sla_remaining_seconds = int((deadline_at - timezone.now()).total_seconds())
            if sla_remaining_seconds <= 0:
                sla_level = 'overdue'
            elif sla_remaining_seconds <= self.SLA_WARNING_HOURS * 3600:
                sla_level = 'warning'

        latest_action_obj = instance.action_logs.select_related('actor').order_by('-created_at', '-id').first()
        latest_action = None
        if latest_action_obj:
            latest_action = {
                'action': latest_action_obj.action,
                'actor_name': getattr(latest_action_obj.actor, 'username', ''),
                'comment': latest_action_obj.comment,
                'created_at': latest_action_obj.created_at,
            }

        return {
            'instance_id': instance.id,
            'target_type': instance.target_type,
            'target_id': instance.object_id,
            'target_title': target_title,
            'instance_status': instance.status,
            'started_by': instance.started_by_id,
            'started_by_name': getattr(instance.started_by, 'username', ''),
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
            'current_step': instance.current_step,
            'current_step_name': current_step_name,
            'current_approvers': current_approvers,
            'current_approver_names': [item['username'] for item in current_approvers],
            'my_last_action_status': my_last_task.status if my_last_task else '',
            'my_last_action_comment': my_last_task.comment if my_last_task else '',
            'my_last_action_at': (
                my_last_task.decided_at or my_last_task.updated_at or my_last_task.created_at
                if my_last_task else None
            ),
            'my_pending_task_ids': [task.id for task in my_pending_tasks],
            'my_pending_task_count': len(my_pending_tasks),
            'sla_deadline_at': sla_deadline_at,
            'sla_remaining_seconds': sla_remaining_seconds,
            'sla_level': sla_level,
            'latest_action': latest_action,
        }

    def _scoped_instances_queryset(self, user):
        queryset = models.ApprovalInstance.objects.select_related('started_by', 'region')
        if not user or user.is_anonymous:
            return queryset.none()
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset
        scope_filter = Q(started_by=user) | Q(tasks__assignee=user)
        if region_ids:
            scope_filter = scope_filter | Q(region_id__in=region_ids)
        return queryset.filter(scope_filter).distinct()

    def _parse_date(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _match_keyword(self, item, keyword):
        target_id = str(item.get('target_id') or '')
        instance_id = str(item.get('instance_id') or '')
        title = str(item.get('target_title') or '').lower()
        return keyword in title or keyword in target_id or keyword in instance_id

    def _dt_to_ts(self, value):
        if not value:
            return 0
        try:
            return value.timestamp()
        except Exception:
            return 0


class ApprovalTaskViewSet(RegionScopedViewSet):
    queryset = models.ApprovalTask.objects.select_related('instance', 'step', 'assignee')
    serializer_class = serializers.ApprovalTaskSerializer
    scope_region_field = 'instance__region'
    scope_owner_field = 'assignee'
    filterset_fields = ['status', 'instance__target_type']
    ordering_fields = ['created_at', 'decided_at']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = models.ApprovalTask.objects.select_related('instance', 'step', 'assignee')
        user = self.request.user
        if not user or user.is_anonymous:
            return queryset.none()
        if user.is_superuser:
            return queryset
        region_ids = scoping.get_region_scope_ids(user)
        if region_ids is None:
            return queryset

        scope_filter = Q(assignee=user) | Q(instance__started_by=user)
        if region_ids:
            scope_filter = scope_filter | Q(instance__region_id__in=region_ids)
        return queryset.filter(scope_filter).distinct()

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

    @action(detail=True, methods=['get'], url_path='detail', url_name='detail')
    def task_detail_action(self, request, pk=None):
        task = self.get_object()
        data = engine.get_task_detail(task, request=request)
        return Response(data)

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        task = self.get_object()
        assignee_id = request.data.get('assignee_id')
        if not assignee_id:
            return Response({'detail': 'assignee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        target_user = core_models.User.objects.filter(id=assignee_id, is_active=True).first()
        if not target_user:
            return Response({'detail': 'assignee not found'}, status=status.HTTP_400_BAD_REQUEST)
        comment = request.data.get('comment', '')
        try:
            new_task = engine.transfer_task(task, request.user, target_user, comment=comment)
        except (PermissionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ApprovalTaskSerializer(new_task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_sign(self, request, pk=None):
        task = self.get_object()
        assignee_id = request.data.get('assignee_id')
        if not assignee_id:
            return Response({'detail': 'assignee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        target_user = core_models.User.objects.filter(id=assignee_id, is_active=True).first()
        if not target_user:
            return Response({'detail': 'assignee not found'}, status=status.HTTP_400_BAD_REQUEST)
        comment = request.data.get('comment', '')
        try:
            new_task = engine.add_sign_task(task, request.user, target_user, comment=comment)
        except (PermissionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ApprovalTaskSerializer(new_task).data, status=status.HTTP_201_CREATED)

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from approval import models
from core import models as core_models

User = get_user_model()


class ApprovalStepSerializer(serializers.ModelSerializer):
    approver_role_name = serializers.CharField(source='approver_role.name', read_only=True)
    approver_user_name = serializers.CharField(source='approver_user.username', read_only=True)

    class Meta:
        model = models.ApprovalStep
        fields = [
            'id',
            'flow',
            'order',
            'name',
            'assignee_type',
            'assignee_scope',
            'approver_role',
            'approver_role_name',
            'approver_user',
            'approver_user_name',
        ]

    def validate(self, attrs):
        assignee_type = attrs.get('assignee_type')
        assignee_scope = attrs.get('assignee_scope', models.ApprovalStep.ASSIGNEE_SCOPE_REGION)
        approver_role = attrs.get('approver_role')
        approver_user = attrs.get('approver_user')
        assignee_type_explicit = 'assignee_type' in getattr(self, 'initial_data', {})

        if self.instance:
            assignee_type = assignee_type or self.instance.assignee_type
            assignee_scope = assignee_scope or self.instance.assignee_scope
            if approver_role is None and 'approver_role' not in attrs:
                approver_role = self.instance.approver_role
            if approver_user is None and 'approver_user' not in attrs:
                approver_user = self.instance.approver_user
        elif not assignee_type_explicit and approver_user and not approver_role:
            assignee_type = models.ApprovalStep.ASSIGNEE_TYPE_USER
            attrs['assignee_type'] = models.ApprovalStep.ASSIGNEE_TYPE_USER
            attrs['assignee_scope'] = models.ApprovalStep.ASSIGNEE_SCOPE_REGION

        if assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_USER:
            if not approver_user:
                raise serializers.ValidationError({'approver_user': '指定用户节点必须配置审批人。'})
            if approver_role:
                raise serializers.ValidationError({'approver_role': '指定用户节点不能配置审批角色。'})
            if assignee_scope != models.ApprovalStep.ASSIGNEE_SCOPE_REGION:
                raise serializers.ValidationError({'assignee_scope': '指定用户节点作用域必须为区域。'})
        elif assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_ROLE:
            if not approver_role:
                raise serializers.ValidationError({'approver_role': '指定角色节点必须配置审批角色。'})
            if approver_user:
                raise serializers.ValidationError({'approver_user': '指定角色节点不能配置审批人。'})
            if assignee_scope not in (
                models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                models.ApprovalStep.ASSIGNEE_SCOPE_GLOBAL,
            ):
                raise serializers.ValidationError({'assignee_scope': '指定角色节点作用域非法。'})
        else:
            raise serializers.ValidationError({'assignee_type': '审批人类型非法。'})
        return attrs


class ApprovalFlowSerializer(serializers.ModelSerializer):
    region_ids = serializers.PrimaryKeyRelatedField(
        source='regions',
        queryset=core_models.Region.objects.all(),
        many=True,
        required=False,
    )
    steps = ApprovalStepSerializer(many=True, read_only=True)

    class Meta:
        model = models.ApprovalFlow
        fields = [
            'id',
            'name',
            'target_type',
            'region',
            'scope_mode',
            'region_ids',
            'is_active',
            'created_at',
            'updated_at',
            'steps',
        ]

    def validate(self, attrs):
        scope_mode = attrs.get('scope_mode')
        regions = attrs.get('regions')
        if self.instance:
            scope_mode = scope_mode or self.instance.scope_mode
            if regions is None:
                regions = self.instance.regions.all()

        if scope_mode == models.ApprovalFlow.SCOPE_SELECTED_REGIONS:
            if not regions:
                raise serializers.ValidationError({'region_ids': '指定区域范围必须至少选择一个区域。'})
        elif scope_mode == models.ApprovalFlow.SCOPE_ALL_REGIONS:
            pass
        else:
            raise serializers.ValidationError({'scope_mode': '适用范围非法。'})
        return attrs


class ApprovalFlowConfigStepSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    order = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(max_length=200)
    assignee_type = serializers.ChoiceField(choices=models.ApprovalStep.ASSIGNEE_TYPE_CHOICES)
    assignee_scope = serializers.ChoiceField(
        choices=models.ApprovalStep.ASSIGNEE_SCOPE_CHOICES,
        default=models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
    )
    approver_role = serializers.PrimaryKeyRelatedField(
        queryset=core_models.Role.objects.all(),
        required=False,
        allow_null=True,
    )
    approver_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        assignee_type = attrs.get('assignee_type')
        assignee_scope = attrs.get('assignee_scope', models.ApprovalStep.ASSIGNEE_SCOPE_REGION)
        approver_role = attrs.get('approver_role')
        approver_user = attrs.get('approver_user')

        if assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_USER:
            if not approver_user:
                raise serializers.ValidationError({'approver_user': '指定用户节点必须配置审批人。'})
            if approver_role:
                raise serializers.ValidationError({'approver_role': '指定用户节点不能配置审批角色。'})
            if assignee_scope != models.ApprovalStep.ASSIGNEE_SCOPE_REGION:
                raise serializers.ValidationError({'assignee_scope': '指定用户节点作用域必须为区域。'})
        elif assignee_type == models.ApprovalStep.ASSIGNEE_TYPE_ROLE:
            if not approver_role:
                raise serializers.ValidationError({'approver_role': '指定角色节点必须配置审批角色。'})
            if approver_user:
                raise serializers.ValidationError({'approver_user': '指定角色节点不能配置审批人。'})
        else:
            raise serializers.ValidationError({'assignee_type': '审批人类型非法。'})
        return attrs


class ApprovalFlowConfigSerializer(serializers.ModelSerializer):
    region_ids = serializers.PrimaryKeyRelatedField(
        source='regions',
        queryset=core_models.Region.objects.all(),
        many=True,
        required=False,
    )
    steps = ApprovalFlowConfigStepSerializer(many=True)

    class Meta:
        model = models.ApprovalFlow
        fields = [
            'id',
            'name',
            'target_type',
            'scope_mode',
            'region_ids',
            'is_active',
            'steps',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_target_type(self, value):
        if value not in (models.ApprovalFlow.TARGET_CONTRACT, models.ApprovalFlow.TARGET_INVOICE):
            raise serializers.ValidationError('当前仅支持合同和开票审批配置。')
        return value

    def validate(self, attrs):
        steps = attrs.get('steps', None)
        if self.instance and steps is None:
            raise serializers.ValidationError({'steps': '必须提交完整步骤配置。'})
        if steps is not None and len(steps) == 0:
            raise serializers.ValidationError({'steps': '至少需要一个审批节点。'})

        scope_mode = attrs.get('scope_mode')
        regions = attrs.get('regions')
        if self.instance:
            scope_mode = scope_mode or self.instance.scope_mode
            if regions is None:
                regions = self.instance.regions.all()

        if scope_mode == models.ApprovalFlow.SCOPE_SELECTED_REGIONS and not regions:
            raise serializers.ValidationError({'region_ids': '指定区域范围必须至少选择一个区域。'})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        steps = instance.steps.select_related('approver_role', 'approver_user').order_by('order', 'id')
        data['steps'] = [
            {
                'id': step.id,
                'order': step.order,
                'name': step.name,
                'assignee_type': step.assignee_type,
                'assignee_scope': step.assignee_scope,
                'approver_role': step.approver_role_id,
                'approver_role_name': step.approver_role.name if step.approver_role else '',
                'approver_user': step.approver_user_id,
                'approver_user_name': step.approver_user.username if step.approver_user else '',
            }
            for step in steps
        ]
        return data

    @transaction.atomic
    def create(self, validated_data):
        steps_data = validated_data.pop('steps')
        regions = validated_data.pop('regions', [])
        flow = models.ApprovalFlow.objects.create(**validated_data)
        if regions:
            flow.regions.set(regions)
        self._upsert_steps(flow, steps_data)
        return flow

    @transaction.atomic
    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps')
        regions = validated_data.pop('regions', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if regions is not None:
            instance.regions.set(regions)
        self._upsert_steps(instance, steps_data)
        return instance

    def _upsert_steps(self, flow, steps_data):
        existing = {item.id: item for item in flow.steps.all()}
        keep_ids = []
        for index, step_data in enumerate(steps_data, start=1):
            step_id = step_data.pop('id', None)
            step_data['order'] = index
            if step_data.get('assignee_type') == models.ApprovalStep.ASSIGNEE_TYPE_USER:
                step_data['assignee_scope'] = models.ApprovalStep.ASSIGNEE_SCOPE_REGION
            if step_id and step_id in existing:
                step = existing[step_id]
                for key, value in step_data.items():
                    setattr(step, key, value)
                step.full_clean()
                step.save()
                keep_ids.append(step.id)
            else:
                step = models.ApprovalStep(flow=flow, **step_data)
                step.full_clean()
                step.save()
                keep_ids.append(step.id)
        flow.steps.exclude(id__in=keep_ids).delete()


class ApprovalInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ApprovalInstance
        fields = '__all__'


class ApprovalTaskSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source='step.name', read_only=True)
    step_order = serializers.IntegerField(source='step.order', read_only=True)
    instance_id = serializers.IntegerField(source='instance.id', read_only=True)
    target_type = serializers.CharField(source='instance.target_type', read_only=True)
    started_by = serializers.IntegerField(source='instance.started_by_id', read_only=True)
    started_by_name = serializers.CharField(source='instance.started_by.username', read_only=True)
    target_id = serializers.IntegerField(source='instance.object_id', read_only=True)
    target_title = serializers.SerializerMethodField()

    class Meta:
        model = models.ApprovalTask
        fields = '__all__'

    def get_target_title(self, obj):
        from approval.adapters import registry

        instance = obj.instance
        target_obj = instance.content_object
        adapter = registry.get_adapter_for_type(instance.target_type)
        if adapter and target_obj:
            return adapter.get_title(target_obj)
        return f"{instance.target_type} #{instance.object_id}"

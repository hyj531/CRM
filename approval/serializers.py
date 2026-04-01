from rest_framework import serializers

from approval import models


class ApprovalFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ApprovalFlow
        fields = '__all__'


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ApprovalStep
        fields = '__all__'


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

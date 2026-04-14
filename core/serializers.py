from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from rest_framework.reverse import reverse
from django.db.models import Sum

from core import models
from core.services import approval_switches

User = get_user_model()


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Region
        fields = '__all__'


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Role
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(
        queryset=models.Role.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'region', 'role', 'roles',
            'dingtalk_user_id', 'dingtalk_union_id', 'phone', 'password'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def _pop_role_payload(self, validated_data):
        roles_value = validated_data.pop('roles', serializers.empty)
        role_value = validated_data.pop('role', serializers.empty)
        return roles_value, role_value

    def _apply_role_payload(self, user, roles_value, role_value):
        if roles_value is not serializers.empty:
            user.roles.set(roles_value)
            primary_role_id = roles_value[0].id if roles_value else None
            if user.role_id != primary_role_id:
                user.role_id = primary_role_id
                user.save(update_fields=['role'])
            return

        if role_value is serializers.empty:
            return

        if role_value is None:
            user.roles.clear()
            if user.role_id is not None:
                user.role_id = None
                user.save(update_fields=['role'])
            return

        if user.role_id != role_value.id:
            user.role_id = role_value.id
            user.save(update_fields=['role'])
        user.roles.set([role_value])

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        roles_value, role_value = self._pop_role_payload(validated_data)
        if roles_value is not serializers.empty:
            validated_data['role'] = roles_value[0] if roles_value else None
        elif role_value is not serializers.empty:
            validated_data['role'] = role_value
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        self._apply_role_payload(user, roles_value, role_value)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', serializers.empty)
        roles_value, role_value = self._pop_role_payload(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password is not serializers.empty:
            if password:
                instance.set_password(password)
            else:
                instance.set_unusable_password()

        instance.save()
        self._apply_role_payload(instance, roles_value, role_value)
        return instance


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Lead
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
        }


class AccountSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = models.Account
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }

    def validate(self, attrs):
        lookup_map = {
            'customer_level': 'customer_level',
            'enterprise_nature': 'enterprise_nature',
        }
        for field, category_code in lookup_map.items():
            option = attrs.get(field)
            if option and option.category.code != category_code:
                raise serializers.ValidationError({field: f'Invalid lookup category: {category_code}'})
        return attrs


class ContactSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = models.Contact
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }


class LookupOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LookupOption
        fields = ['id', 'code', 'name', 'is_active', 'sort_order', 'category']


class LookupCategorySerializer(serializers.ModelSerializer):
    options = LookupOptionSerializer(many=True, read_only=True)

    class Meta:
        model = models.LookupCategory
        fields = ['id', 'code', 'name', 'is_active', 'sort_order', 'options']


class OpportunitySerializer(serializers.ModelSerializer):
    stage_stay_days = serializers.SerializerMethodField(read_only=True)
    account_name = serializers.SerializerMethodField(read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = models.Opportunity
        fields = '__all__'
        extra_kwargs = {
            'stage_entered_at': {'read_only': True},
            'owner': {'required': False},
            'region': {'required': False},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }

    def get_stage_stay_days(self, obj):
        if not obj.stage_entered_at:
            return None
        from django.utils import timezone
        delta = timezone.now().date() - obj.stage_entered_at.date()
        return max(delta.days, 0)

    def get_account_name(self, obj):
        account = getattr(obj, 'account', None)
        if not account:
            return ''
        return account.full_name or account.short_name or getattr(account, 'name', '') or ''

    def validate(self, attrs):
        lookup_map = {
            'product_need': 'product_need',
            'user_group': 'user_group',
            'opportunity_category': 'opportunity_category',
            'customer_level': 'customer_level',
            'lead_source': 'lead_source',
            'enterprise_nature': 'enterprise_nature',
        }
        for field, category_code in lookup_map.items():
            option = attrs.get(field)
            if option and option.category.code != category_code:
                raise serializers.ValidationError({field: f'Invalid lookup category: {category_code}'})
        return attrs

    def _apply_stage_defaults(self, attrs, instance=None):
        stage = attrs.get('stage') or (instance.stage if instance else models.Opportunity.STAGE_LEAD)
        default_probs = {
            models.Opportunity.STAGE_LEAD: 5,
            models.Opportunity.STAGE_OPPORTUNITY: 15,
            models.Opportunity.STAGE_DEMAND: 10,
            models.Opportunity.STAGE_SOLUTION: 30,
            models.Opportunity.STAGE_BUSINESS: 70,
            models.Opportunity.STAGE_CONTRACT: 90,
            models.Opportunity.STAGE_WON: 100,
            models.Opportunity.STAGE_FRAMEWORK: 100,
            models.Opportunity.STAGE_LOST: 0,
        }
        if 'win_probability' not in attrs or attrs.get('win_probability') is None:
            attrs['win_probability'] = default_probs.get(stage, 0)
        return attrs

    def create(self, validated_data):
        validated_data = self._apply_stage_defaults(validated_data)
        if not validated_data.get('stage_entered_at'):
            from django.utils import timezone
            validated_data['stage_entered_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        stage_changed = 'stage' in validated_data and validated_data['stage'] != instance.stage
        validated_data = self._apply_stage_defaults(validated_data, instance=instance)
        if stage_changed:
            from django.utils import timezone
            validated_data['stage_entered_at'] = timezone.now()
        return super().update(instance, validated_data)


class OpportunityAttachmentSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.OpportunityAttachment
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'original_name': {'required': False},
        }

    def get_file_url(self, obj):
        if not obj.file:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

class ActivitySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = models.Activity
        fields = '__all__'
        extra_kwargs = {
            'owner': {'read_only': True},
            'region': {'read_only': True},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Task
        fields = '__all__'


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Quote
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
        }


class ContractSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    paid_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    receivable_amount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.Contract
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }

    def _approval_status_managed_by_system(self):
        return approval_switches.is_contract_approval_enabled()

    def _latest_approval_instance_status(self, instance):
        from approval import models as approval_models

        content_type = ContentType.objects.get_for_model(instance.__class__)
        pending_exists = approval_models.ApprovalInstance.objects.filter(
            content_type=content_type,
            object_id=instance.id,
            status=approval_models.ApprovalInstance.STATUS_PENDING,
        ).exists()
        if pending_exists:
            return approval_models.ApprovalInstance.STATUS_PENDING

        latest_instance = (
            approval_models.ApprovalInstance.objects
            .filter(content_type=content_type, object_id=instance.id)
            .order_by('-created_at', '-id')
            .first()
        )
        return latest_instance.status if latest_instance else None

    def _is_value_changed(self, instance, field_name, incoming_value):
        current_value = getattr(instance, field_name, None)
        current_cmp = getattr(current_value, 'pk', current_value)
        incoming_cmp = getattr(incoming_value, 'pk', incoming_value)
        return current_cmp != incoming_cmp

    def _collect_changed_fields(self, instance, validated_data):
        changed = []
        for field_name, incoming_value in validated_data.items():
            if self._is_value_changed(instance, field_name, incoming_value):
                changed.append(field_name)
        return changed

    def get_fields(self):
        fields = super().get_fields()
        if self._approval_status_managed_by_system() and 'approval_status' in fields:
            fields['approval_status'].read_only = True
        return fields

    def validate(self, attrs):
        vendor = attrs.get('vendor_company')
        if vendor and vendor.category.code != 'vendor_company':
            raise serializers.ValidationError({'vendor_company': 'Invalid lookup category: vendor_company'})
        framework_contract = attrs.get('framework_contract')
        if framework_contract:
            if not framework_contract.is_framework:
                raise serializers.ValidationError({'framework_contract': '所属框架合同必须为框架合同'})
            if self.instance and framework_contract.id == self.instance.id:
                raise serializers.ValidationError({'framework_contract': '所属框架合同不能为自身'})
        return attrs

    def create(self, validated_data):
        if self._approval_status_managed_by_system():
            validated_data.pop('approval_status', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'contract_no' in validated_data:
            request = self.context.get('request')
            user = getattr(request, 'user', None)
            is_admin = bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
            if not is_admin:
                raise serializers.ValidationError({'contract_no': '仅管理员可修改合同编号'})
        if self._approval_status_managed_by_system():
            validated_data.pop('approval_status', None)
            approval_instance_status = self._latest_approval_instance_status(instance)
            changed_fields = [
                name
                for name in self._collect_changed_fields(instance, validated_data)
                if name not in {'updated_by', 'updated_at', 'created_by', 'created_at'}
            ]

            if approval_instance_status == 'pending' and changed_fields:
                raise serializers.ValidationError({'detail': '合同审批中，主信息为只读。'})

            if (
                instance.approval_status == 'approved'
                and approval_instance_status == 'approved'
            ):
                disallowed_fields = [name for name in changed_fields if name != 'signed_at']
                if disallowed_fields:
                    raise serializers.ValidationError({
                        'detail': '合同已审批通过，仅允许修改签署日期。请先发起修订后再修改其它字段并重新提交审批。'
                    })
        return super().update(instance, validated_data)

    def get_receivable_amount(self, obj):
        paid_total = getattr(obj, 'paid_total', None)
        if paid_total is None:
            paid_total = obj.payments.aggregate(total=Sum('amount')).get('total') or 0
        base = obj.current_output if obj.current_output is not None else obj.amount
        if base is None:
            return None
        return base - paid_total


class ContractAttachmentSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.ContractAttachment
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'original_name': {'required': False},
        }

    def get_file_url(self, obj):
        if not obj.file:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


class InvoiceSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = models.Invoice
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
        }

    def _approval_status_managed_by_system(self):
        return approval_switches.is_invoice_approval_enabled()

    def get_fields(self):
        fields = super().get_fields()
        if self._approval_status_managed_by_system() and 'approval_status' in fields:
            fields['approval_status'].read_only = True
        return fields

    def create(self, validated_data):
        if self._approval_status_managed_by_system():
            validated_data.pop('approval_status', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if self._approval_status_managed_by_system():
            validated_data.pop('approval_status', None)
        return super().update(instance, validated_data)


class PaymentSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = models.Payment
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
            'created_by': {'read_only': True},
        }


class CommonDocDirectorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    can_view = serializers.SerializerMethodField(read_only=True)
    can_download = serializers.SerializerMethodField(read_only=True)
    can_upload = serializers.SerializerMethodField(read_only=True)
    can_edit = serializers.SerializerMethodField(read_only=True)
    can_delete = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.CommonDocDirectory
        fields = '__all__'
        extra_kwargs = {
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }

    def _permission(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        if user.is_staff or user.is_superuser:
            return 'admin'
        permission_map = self.context.get('directory_permission_map', {})
        return permission_map.get(obj.id)

    def _flag(self, perm, key):
        if perm == 'admin':
            return True
        if isinstance(perm, dict):
            return bool(perm.get(key))
        return bool(perm and getattr(perm, key, False))

    def get_can_view(self, obj):
        perm = self._permission(obj)
        return self._flag(perm, 'can_view')

    def get_can_download(self, obj):
        perm = self._permission(obj)
        return self._flag(perm, 'can_download')

    def get_can_upload(self, obj):
        perm = self._permission(obj)
        return self._flag(perm, 'can_upload')

    def get_can_edit(self, obj):
        perm = self._permission(obj)
        return self._flag(perm, 'can_edit')

    def get_can_delete(self, obj):
        perm = self._permission(obj)
        return self._flag(perm, 'can_delete')


class CommonDocDirectoryPermissionSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = models.CommonDocDirectoryPermission
        fields = '__all__'


class CommonDocumentSerializer(serializers.ModelSerializer):
    directory_name = serializers.CharField(source='directory.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    download_url = serializers.SerializerMethodField(read_only=True)
    file_size = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.CommonDocument
        fields = '__all__'
        extra_kwargs = {
            'original_name': {'read_only': True},
            'created_by': {'read_only': True},
            'updated_by': {'read_only': True},
        }

    def get_download_url(self, obj):
        request = self.context.get('request')
        url = reverse('common-document-download', kwargs={'pk': obj.pk}, request=request)
        return url

    def get_file_size(self, obj):
        try:
            return int(obj.file.size) if obj.file else 0
        except Exception:
            return 0


class DingTalkSyncRequestSerializer(serializers.Serializer):
    departments = serializers.ListField(child=serializers.DictField(), required=False)
    users = serializers.ListField(child=serializers.DictField(), required=False)


class DingTalkSyncResultSerializer(serializers.Serializer):
    departments_total = serializers.IntegerField()
    departments_created = serializers.IntegerField()
    departments_updated = serializers.IntegerField()
    departments_parent_updated = serializers.IntegerField()
    users_total = serializers.IntegerField()
    users_created = serializers.IntegerField()
    users_updated = serializers.IntegerField()

from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.db.models import Sum

from core import models

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
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'region', 'role',
            'dingtalk_user_id', 'dingtalk_union_id', 'phone', 'password'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user


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

    class Meta:
        model = models.Contact
        fields = '__all__'
        extra_kwargs = {
            'owner': {'required': False},
            'region': {'required': False},
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

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import redirect
from django.urls import path

from core import models
from core.services import approval_switches, dingtalk_sync


@admin.register(models.Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('owner', request.user.pk)
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


class RolePermissionInline(admin.TabularInline):
    model = models.RolePermission
    fields = ('module', 'can_create', 'can_update', 'can_delete', 'can_approve')
    readonly_fields = ('module',)
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        module_order = [
            When(module=module_code, then=Value(index))
            for index, (module_code, _) in enumerate(models.RolePermission.MODULE_CHOICES)
        ]
        return queryset.annotate(
            _module_order=Case(*module_order, default=Value(999), output_field=IntegerField())
        ).order_by('_module_order', 'id')


@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'data_scope')
    search_fields = ('name', 'code')
    inlines = [RolePermissionInline]

    def _ensure_role_permissions(self, role):
        for module_code, _ in models.RolePermission.MODULE_CHOICES:
            models.RolePermission.objects.get_or_create(role=role, module=module_code)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._ensure_role_permissions(obj)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        role = self.get_object(request, object_id)
        if role:
            self._ensure_role_permissions(role)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)


@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ('username', 'email', 'is_staff', 'is_active', 'role', 'display_roles', 'region')
    list_filter = ('is_staff', 'is_active', 'role', 'roles', 'region')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    filter_horizontal = ('roles', 'groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('组织与权限', {'fields': ('region', 'role', 'roles', 'groups', 'user_permissions')}),
        ('状态', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'phone', 'region', 'role', 'roles', 'is_staff', 'is_active'),
        }),
    )
    change_list_template = 'admin/core/user/change_list.html'

    @admin.display(description='角色列表')
    def display_roles(self, obj):
        names = list(obj.roles.order_by('id').values_list('name', flat=True))
        if names:
            return ' / '.join(names)
        if obj.role_id:
            return obj.role.name
        return '-'

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        role_ids = list(user.roles.order_by('id').values_list('id', flat=True))
        if role_ids:
            primary_role_id = role_ids[0]
            if user.role_id != primary_role_id:
                user.role_id = primary_role_id
                user.save(update_fields=['role'])
            return
        if user.role_id:
            user.roles.set([user.role_id])

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('sync-dingtalk/', self.admin_site.admin_view(self.sync_dingtalk), name='core_user_sync_dingtalk'),
        ]
        return custom + urls

    def sync_dingtalk(self, request):
        if not request.user.is_staff:
            self.message_user(request, '无权限执行钉钉同步。', level=messages.ERROR)
            return redirect('..')
        summary = dingtalk_sync.sync_departments_and_users()
        self.message_user(
            request,
            (
                '钉钉同步完成。部门：总数={total}，新增={created}，更新={updated}，父级更新={parent_updated}；'
                '用户：总数={u_total}，新增={u_created}，更新={u_updated}'
            ).format(
                total=summary['departments_total'],
                created=summary['departments_created'],
                updated=summary['departments_updated'],
                parent_updated=summary['departments_parent_updated'],
                u_total=summary['users_total'],
                u_created=summary['users_created'],
                u_updated=summary['users_updated'],
            ),
            level=messages.SUCCESS,
        )
        return redirect('..')


@admin.register(models.ApprovalModuleSetting)
class ApprovalModuleSettingAdmin(admin.ModelAdmin):
    list_display = ('contract_approval_enabled', 'invoice_approval_enabled', 'updated_at')
    readonly_fields = ('singleton_key', 'created_at', 'updated_at')
    fieldsets = (
        ('审批开关', {'fields': ('contract_approval_enabled', 'invoice_approval_enabled')}),
        ('系统字段', {'fields': ('singleton_key', 'created_at', 'updated_at')}),
    )

    def has_add_permission(self, request):
        has_base_permission = super().has_add_permission(request)
        if not has_base_permission:
            return False
        return not models.ApprovalModuleSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.singleton_key = models.ApprovalModuleSetting.SINGLETON_KEY_DEFAULT
        super().save_model(request, obj, form, change)
        approval_switches.clear_approval_switches_cache()


admin.site.register(models.Region)
admin.site.register(models.RolePermission)
admin.site.register(models.Lead)
admin.site.register(models.Account)
admin.site.register(models.OpportunityAttachment)
admin.site.register(models.ContractAttachment)
admin.site.register(models.Contact)
admin.site.register(models.LookupCategory)
admin.site.register(models.LookupOption)
admin.site.register(models.Activity)
admin.site.register(models.Task)
admin.site.register(models.Quote)
admin.site.register(models.Contract)
admin.site.register(models.Invoice)
admin.site.register(models.Payment)
admin.site.register(models.CommonDocDirectory)
admin.site.register(models.CommonDocDirectoryPermission)
admin.site.register(models.CommonDocument)

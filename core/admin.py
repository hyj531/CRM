from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.shortcuts import redirect
from django.urls import path

from core import models
from core.services import dingtalk_sync


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


@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ('username', 'email', 'is_staff', 'is_active', 'role', 'region')
    list_filter = ('is_staff', 'is_active', 'role', 'region')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('组织与权限', {'fields': ('region', 'role', 'groups', 'user_permissions')}),
        ('状态', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'phone', 'region', 'role', 'is_staff', 'is_active'),
        }),
    )
    change_list_template = 'admin/core/user/change_list.html'

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


admin.site.register(models.Region)
admin.site.register(models.Role)
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

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core import models


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
admin.site.register(models.ApprovalFlow)
admin.site.register(models.ApprovalStep)
admin.site.register(models.ApprovalInstance)
admin.site.register(models.ApprovalTask)

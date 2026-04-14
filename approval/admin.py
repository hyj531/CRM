from django.contrib import admin

from approval import models

admin.site.register(models.ApprovalFlow)
admin.site.register(models.ApprovalStep)
admin.site.register(models.ApprovalInstance)
admin.site.register(models.ApprovalTask)
admin.site.register(models.ApprovalActionLog)
admin.site.register(models.ApprovalTodoOutbox)

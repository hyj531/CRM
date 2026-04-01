from django.apps import AppConfig


class ApprovalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'approval'
    verbose_name = '审批引擎'

    def ready(self):
        from approval import adapters  # noqa: F401

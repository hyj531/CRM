class BaseApprovalAdapter:
    target_type = ''
    model = None

    def get_target_type(self):
        return self.target_type

    def get_region(self, obj):
        return getattr(obj, 'region', None)

    def get_display_fields(self, obj):
        return []

    def get_title(self, obj):
        return f"{self.target_type} #{getattr(obj, 'id', '')}".strip()

    def set_approval_status(self, obj, status):
        return obj

    def get_attachments(self, obj, request=None):
        return []

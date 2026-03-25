from django.contrib.auth import get_user_model

User = get_user_model()


class DingTalkBackend:
    """
    Authenticate a user by DingTalk user id. This is used by the SSO endpoint.
    """

    def authenticate(self, request, dingtalk_user_id=None, **kwargs):
        if not dingtalk_user_id:
            return None
        return User.objects.filter(dingtalk_user_id=dingtalk_user_id, is_active=True).first()

    def get_user(self, user_id):
        return User.objects.filter(id=user_id, is_active=True).first()

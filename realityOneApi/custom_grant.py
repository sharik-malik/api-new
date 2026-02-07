from oauthlib.oauth2 import RequestValidator, Server
from oauth2_provider.oauth2_backends import OAuthLibCore
from oauth2_provider.models import AccessToken, Application
from django.utils.timezone import now
from datetime import timedelta
from django.contrib.auth import get_user_model

class UserIDGrant(RequestValidator):
    def validate_user(self, user_id, client, request, *args, **kwargs):
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            request.user = user
            return True
        except User.DoesNotExist:
            return False

    def save_bearer_token(self, token, request, *args, **kwargs):
        AccessToken.objects.create(
            user=request.user,
            token=token['access_token'],
            application=request.client,
            expires=now() + timedelta(seconds=3600),
            scope=token['scope'],
        )

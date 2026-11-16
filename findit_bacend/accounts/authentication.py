from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class BlockAwareTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if user.is_blocked:
            raise exceptions.AuthenticationFailed("Akkaunt bloklangan.")
        return user, token
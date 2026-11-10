import logging

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.roles import roles_of
from accounts.user_admin import must_change_password

logger = logging.getLogger("accounts")


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    must_change_password = serializers.SerializerMethodField()

    def get_full_name(self, user) -> str:
        return user.get_full_name() or user.get_username()

    def get_must_change_password(self, user) -> bool:
        return must_change_password(user)

    def get_roles(self, user) -> list[str]:
        return roles_of(user)


class LoginSerializer(TokenObtainPairSerializer):
    """Login JWT: devuelve tokens y el usuario con sus roles; registra fallos sin la clave."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["roles"] = roles_of(user)
        return token

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except Exception:
            logger.warning("API: acceso fallido usuario=%s", attrs.get(self.username_field, ""))
            raise
        data["user"] = UserSerializer(self.user).data
        logger.info("API: acceso correcto usuario=%s", self.user.get_username())
        return data

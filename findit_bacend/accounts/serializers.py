from django.contrib.auth import authenticate, get_user_model, password_validation
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("id", "username", "email", "phone", "first_name", "last_name", "password")

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        # rol har doim "user", ro'yxatdan o'tishda o'zgartirib bo'lmaydi
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Login yoki parol noto'g'ri.")
        if user.is_blocked:
            reason = f" Sabab: {user.blocked_reason}" if user.blocked_reason else ""
            raise serializers.ValidationError("Akkaunt bloklangan." + reason)
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "username", "email", "phone", "first_name", "last_name",
            "role", "is_blocked", "date_joined",
        )
        read_only_fields = ("id", "username", "role", "is_blocked", "date_joined")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Eski parol noto'g'ri.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value
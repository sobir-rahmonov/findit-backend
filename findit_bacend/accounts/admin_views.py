from rest_framework import mixins, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from notifications.models import Notification
from notifications.services import notify

from .admin_serializers import AdminUserSerializer, BlockSerializer, RoleSerializer
from .models import User
from .permissions import IsAdministrator


class AdminUserViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdministrator]
    filterset_fields = ["role", "is_blocked", "is_active"]
    search_fields = ["username", "email", "phone", "first_name", "last_name"]
    ordering_fields = ["date_joined", "username", "last_login"]
    ordering = ["-date_joined"]

    def _respond(self, user):
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        user = self.get_object()
        data = BlockSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        if user.pk == request.user.pk:
            raise ValidationError("O'zingizni bloklay olmaysiz.")
        if user.is_administrator:
            raise ValidationError("Administratorni bloklab bo'lmaydi.")
        if user.is_blocked:
            raise ValidationError("Foydalanuvchi allaqachon bloklangan.")

        user.is_blocked = True
        user.blocked_reason = data.validated_data["reason"][:255]
        user.save(update_fields=["is_blocked", "blocked_reason"])
        Token.objects.filter(user=user).delete()  # darhol tizimdan chiqadi
        return self._respond(user)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        user = self.get_object()
        if not user.is_blocked:
            raise ValidationError("Foydalanuvchi bloklanmagan.")
        user.is_blocked = False
        user.blocked_reason = ""
        user.save(update_fields=["is_blocked", "blocked_reason"])
        return self._respond(user)

    @action(detail=True, methods=["post"], url_path="set-role")
    def set_role(self, request, pk=None):
        user = self.get_object()
        data = RoleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        new_role = data.validated_data["role"]

        if user.pk == request.user.pk:
            raise ValidationError("O'z rolingizni o'zgartira olmaysiz.")
        if user.is_administrator:
            raise ValidationError("Administrator rolini API orqali o'zgartirib bo'lmaydi.")
        if user.role == new_role:
            raise ValidationError("Foydalanuvchi allaqachon shu rolda.")

        user.role = new_role
        user.save()  # is_staff ni save() o'zi moslaydi
        label = user.get_role_display()
        notify(
            user,
            Notification.Kind.SYSTEM,
            "Rolingiz o'zgardi",
            f"Sizning yangi rolingiz: {label}.",
        )
        return self._respond(user)
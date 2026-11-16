from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsModerator(BasePermission):
    """Moderator yoki admin."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_moderator)


class IsAdministrator(BasePermission):
    """Faqat admin."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_administrator)


class IsAdministratorOrReadOnly(BasePermission):
    """Hamma ko'ra oladi, o'zgartirish faqat admin."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_administrator)
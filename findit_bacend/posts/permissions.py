from rest_framework.permissions import BasePermission


class IsAuthorOrAdmin(BasePermission):
    """
    Tahrirlash: faqat muallif.
    O'chirish: muallif yoki admin.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == "DELETE" and user.is_administrator:
            return True
        return obj.author_id == user.id
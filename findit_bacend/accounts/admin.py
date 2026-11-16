from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from rest_framework.authtoken.models import Token

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "phone", "role", "is_blocked", "is_active", "date_joined")
    list_filter = ("role", "is_blocked", "is_active")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    actions = ["block_users", "unblock_users"]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("FindIt", {"fields": ("phone", "role", "is_blocked", "blocked_reason")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("FindIt", {"fields": ("phone", "role")}),
    )

    @admin.action(description="Tanlanganlarni bloklash")
    def block_users(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)  # o'zingizni bloklab bo'lmaydi
        Token.objects.filter(user__in=queryset).delete()  # tizimdan darrov chiqariladi
        count = queryset.update(is_blocked=True)
        self.message_user(request, f"{count} ta foydalanuvchi bloklandi.")

    @admin.action(description="Tanlanganlarni blokdan chiqarish")
    def unblock_users(self, request, queryset):
        count = queryset.update(is_blocked=False, blocked_reason="")
        self.message_user(request, f"{count} ta foydalanuvchi blokdan chiqarildi.")
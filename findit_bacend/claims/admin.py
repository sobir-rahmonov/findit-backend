from django.contrib import admin
from django.utils.html import format_html

from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "claimant", "found_post", "colored_status", "moderator", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("claimant__username", "found_post__title", "description")
    date_hierarchy = "created_at"
    autocomplete_fields = ("found_post", "lost_post", "claimant", "moderator")
    readonly_fields = ("proof_preview", "reviewed_at", "handed_over_at", "created_at", "updated_at")

    fieldsets = (
        ("Da'vo", {"fields": ("found_post", "lost_post", "claimant", "description", "proof_image", "proof_preview")}),
        ("Moderator qarori", {"fields": ("status", "moderator", "moderator_note", "reviewed_at")}),
        ("Topshirish", {"fields": ("handover_note", "handed_over_at")}),
        ("Vaqt", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Isbot rasmi")
    def proof_preview(self, obj):
        if obj.proof_image:
            return format_html(
                '<img src="{}" style="max-width:320px;border-radius:12px;" />', obj.proof_image.url
            )
        return "Rasm yo'q"

    @admin.display(description="Holat", ordering="status")
    def colored_status(self, obj):
        colors = {
            "pending": "#d97706",
            "approved": "#2563eb",
            "rejected": "#dc2626",
            "completed": "#16a34a",
            "cancelled": "#6b7280",
        }
        return format_html(
            '<b style="color:{};">{}</b>', colors.get(obj.status, "#000"), obj.get_status_display()
        )
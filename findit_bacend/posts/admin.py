from django.contrib import admin
from django.utils.html import format_html
from rest_framework.exceptions import ValidationError

from .services import approve_post, reject_post

from .models import Category, Match, Place, Post, Report

POST_STATUS_COLORS = {
    "pending": "#d97706",
    "active": "#16a34a",
    "handover": "#7c3aed",
    "closed": "#6b7280",
    "rejected": "#dc2626",
}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "is_active", "post_count")
    list_editable = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="E'lonlar soni")
    def post_count(self, obj):
        return obj.posts.count()


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "place_type", "address", "latitude", "longitude", "is_active")
    list_editable = ("is_active",)
    list_filter = ("place_type", "is_active")
    search_fields = ("name", "address")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview", "title", "colored_type", "category", "place",
        "colored_status", "author", "event_date", "created_at",
    )
    list_display_links = ("image_preview", "title")
    list_filter = ("type", "status", "category", "place", "color", "created_at")
    search_fields = ("title", "description", "brand", "location_detail", "author__username")
    date_hierarchy = "created_at"
    list_per_page = 20     
    actions = ["approve_selected", "reject_selected"]
    autocomplete_fields = ("author", "category", "place")
    readonly_fields = (
        "image_preview_large", "moderated_by", "moderated_at",
        "closed_at", "created_at", "updated_at",
    )

    fieldsets = (
        ("Asosiy", {"fields": ("type", "author", "title", "description", "category")}),
        ("Buyum belgilari", {"fields": ("color", "brand", "image", "image_preview_large")}),
        ("Joy va sana", {"fields": ("place", "location_detail", ("latitude", "longitude"), "event_date")}),
        ("Topilgan buyum uchun", {"fields": ("storage_note", "private_detail")}),
        ("Holat va moderatsiya", {
            "fields": ("status", "reject_reason", "moderated_by", "moderated_at", "closed_at"),
        }),
        ("Vaqt", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Rasm")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:48px;height:48px;object-fit:cover;border-radius:8px;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="Rasm (ko'rinishi)")
    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:320px;border-radius:12px;" />', obj.image.url
            )
        return "Rasm yuklanmagan"

    @admin.display(description="Turi", ordering="type")
    def colored_type(self, obj):
        color = "#dc2626" if obj.type == "lost" else "#2563eb"
        return format_html('<b style="color:{};">{}</b>', color, obj.get_type_display())

    @admin.display(description="Holat", ordering="status")
    def colored_status(self, obj):
        return format_html(
            '<b style="color:{};">{}</b>',
            POST_STATUS_COLORS.get(obj.status, "#000"),
            obj.get_status_display(),
        )


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "lost_post", "found_post", "score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("lost_post__title", "found_post__title")
    autocomplete_fields = ("lost_post", "found_post")
    readonly_fields = ("reasons", "created_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reason", "post", "target_user", "reporter", "colored_status", "created_at")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("text", "reporter__username", "target_user__username", "post__title")
    autocomplete_fields = ("reporter", "post", "target_user", "handled_by")
    readonly_fields = ("created_at", "handled_at")

    @admin.display(description="Holat", ordering="status")
    def colored_status(self, obj):
        colors = {"open": "#d97706", "resolved": "#16a34a", "dismissed": "#6b7280"}
        return format_html(
            '<b style="color:{};">{}</b>', colors.get(obj.status, "#000"), obj.get_status_display()
        )

    @admin.action(description="Tanlangan e'lonlarni tasdiqlash")
    def approve_selected(self, request, queryset):
        done = 0
        for post in queryset:
            try:
                approve_post(post, request.user)
                done += 1
            except ValidationError:
                continue
        self.message_user(request, f"{done} ta e'lon tasdiqlandi.")

    @admin.action(description="Tanlangan e'lonlarni rad etish")
    def reject_selected(self, request, queryset):
        done = 0
        for post in queryset:
            try:
                reject_post(post, request.user, "Qoidalarga mos kelmaydi.")
                done += 1
            except ValidationError:
                continue
        self.message_user(request, f"{done} ta e'lon rad etildi.")    

    
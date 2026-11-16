from django.utils import timezone
from rest_framework import serializers

from .models import Category, Place, Post


def check_coordinates(attrs, instance=None):
    lat = attrs.get("latitude", getattr(instance, "latitude", None))
    lng = attrs.get("longitude", getattr(instance, "longitude", None))
    if (lat is None) != (lng is None):
        raise serializers.ValidationError("Kenglik va uzunlik birga kiritilishi kerak.")


class CategorySerializer(serializers.ModelSerializer):
    active_posts = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon", "is_active", "active_posts")


class PlaceSerializer(serializers.ModelSerializer):
    place_type_display = serializers.CharField(source="get_place_type_display", read_only=True)

    class Meta:
        model = Place
        fields = (
            "id", "name", "place_type", "place_type_display",
            "address", "latitude", "longitude", "is_active",
        )

    def validate(self, attrs):
        check_coordinates(attrs, self.instance)
        return attrs


class PostSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    color_display = serializers.CharField(source="get_color_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    place_name = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "type", "type_display", "title", "description",
            "category", "category_name", "color", "color_display", "brand",
            "place", "place_name", "location_detail", "latitude", "longitude",
            "event_date", "image", "storage_note", "private_detail",
            "status", "status_display", "reject_reason",
            "author", "author_name", "is_mine", "created_at", "updated_at",
        )
        read_only_fields = ("status", "reject_reason", "author", "created_at", "updated_at")

    def get_place_name(self, obj):
        return obj.place.name if obj.place else None

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.author_id == request.user.id)

    def validate_type(self, value):
        if self.instance and value != self.instance.type:
            raise serializers.ValidationError("E'lon turini o'zgartirib bo'lmaydi.")
        return value

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Bu kategoriya faol emas.")
        return value

    def validate_place(self, value):
        if value is not None and not value.is_active:
            raise serializers.ValidationError("Bu joy faol emas.")
        return value

    def validate_event_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Sana kelajakda bo'lishi mumkin emas.")
        return value

    def validate(self, attrs):
        check_coordinates(attrs, self.instance)

        # Koordinata kiritilmagan bo'lsa, joyning koordinatasi olinadi
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        place = attrs.get("place", getattr(self.instance, "place", None))
        if lat is None and place and place.latitude is not None:
            attrs["latitude"] = place.latitude
            attrs["longitude"] = place.longitude
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        allowed = bool(
            user
            and user.is_authenticated
            and (user.is_moderator or instance.author_id == user.id)
        )
        if not allowed:
            # yashirin belgi va rad etish sababi hamma uchun emas
            data.pop("private_detail", None)
            data.pop("reject_reason", None)
        return data



class ModerationPostSerializer(PostSerializer):
    """Moderator uchun: muallif aloqasi va shikoyatlar soni bilan."""

    author_username = serializers.CharField(source="author.username", read_only=True)
    author_phone = serializers.CharField(source="author.phone", read_only=True)
    moderated_by_name = serializers.SerializerMethodField()
    reports_count = serializers.IntegerField(source="reports.count", read_only=True)

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + (
            "author_username", "author_phone", "moderated_by_name", "reports_count",
        )

    def get_moderated_by_name(self, obj):
        return obj.moderated_by.username if obj.moderated_by else None


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)    
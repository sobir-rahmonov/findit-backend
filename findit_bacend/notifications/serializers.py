from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    post_title = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id", "kind", "kind_display", "title", "message",
            "post", "post_title", "claim", "is_read", "created_at",
        )
        read_only_fields = fields

    def get_post_title(self, obj):
        return obj.post.title if obj.post else None
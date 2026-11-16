from rest_framework import serializers

from .models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = (
            "require_moderation",
            "match_threshold",
            "match_max_distance_km",
            "match_date_window_days",
            "max_active_posts_per_user",
        )

    def validate_match_threshold(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError("1 dan 100 gacha bo'lishi kerak.")
        return value

    def validate_match_max_distance_km(self, value):
        if value <= 0:
            raise serializers.ValidationError("0 dan katta bo'lishi kerak.")
        return value

    def validate_match_date_window_days(self, value):
        if value < 1:
            raise serializers.ValidationError("Kamida 1 kun bo'lishi kerak.")
        return value

    def validate_max_active_posts_per_user(self, value):
        if value < 1:
            raise serializers.ValidationError("Kamida 1 ta bo'lishi kerak.")
        return value
from rest_framework import serializers

from .models import User


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    posts_count = serializers.SerializerMethodField()
    claims_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "full_name", "phone",
            "role", "role_display", "is_blocked", "blocked_reason",
            "is_active", "date_joined", "last_login",
            "posts_count", "claims_count",
        )
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_posts_count(self, obj):
        from posts.models import Post
        return Post.objects.filter(author=obj).count()

    def get_claims_count(self, obj):
        from claims.models import Claim
        return Claim.objects.filter(claimant=obj).count()


class BlockSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[User.Role.USER, User.Role.MODERATOR])
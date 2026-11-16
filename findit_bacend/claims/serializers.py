from rest_framework import serializers

from posts.models import Post
from posts.serializers import PostSerializer

from .models import Claim


class ClaimSerializer(serializers.ModelSerializer):
    found_post_title = serializers.CharField(source="found_post.title", read_only=True)
    lost_post_title = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    pickup_info = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = (
            "id", "found_post", "found_post_title", "lost_post", "lost_post_title",
            "description", "proof_image", "status", "status_display",
            "moderator_note", "pickup_info", "handover_note", "handed_over_at",
            "created_at",
        )
        read_only_fields = (
            "status", "moderator_note", "handover_note", "handed_over_at", "created_at",
        )

    def get_lost_post_title(self, obj):
        return obj.lost_post.title if obj.lost_post else None

    def get_pickup_info(self, obj):
        # Buyum qayerdaligi faqat da'vo tasdiqlangandan keyin ko'rinadi
        if obj.status in (Claim.Status.APPROVED, Claim.Status.COMPLETED):
            return obj.found_post.storage_note
        return None

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError(
                "Buyumni tasdiqlovchi belgilarni batafsilroq yozing (kamida 10 belgi)."
            )
        return value

    def validate_found_post(self, post):
        if post.type != Post.Type.FOUND or post.status != Post.Status.ACTIVE:
            raise serializers.ValidationError("Bu e'longa da'vo yuborib bo'lmaydi.")
        return post

    def validate(self, attrs):
        user = self.context["request"].user
        found = attrs["found_post"]

        if found.author_id == user.id:
            raise serializers.ValidationError("O'z e'loningizga da'vo yubora olmaysiz.")

        lost = attrs.get("lost_post")
        if lost and (
            lost.type != Post.Type.LOST
            or lost.author_id != user.id
            or lost.status != Post.Status.ACTIVE
        ):
            raise serializers.ValidationError(
                {"lost_post": "Faqat o'zingizning faol yo'qolgan e'loningizni tanlang."}
            )

        if Claim.objects.filter(
            found_post=found, claimant=user, status=Claim.Status.PENDING
        ).exists():
            raise serializers.ValidationError(
                "Bu buyum uchun da'voyingiz allaqachon ko'rib chiqilmoqda."
            )
        return attrs


class ModerationClaimSerializer(ClaimSerializer):
    """Moderator uchun: da'vogar, ikkala e'lon (yashirin belgi bilan)."""

    claimant_username = serializers.CharField(source="claimant.username", read_only=True)
    claimant_phone = serializers.CharField(source="claimant.phone", read_only=True)
    claimant_name = serializers.SerializerMethodField()
    moderator_name = serializers.SerializerMethodField()
    found_post_detail = PostSerializer(source="found_post", read_only=True)
    lost_post_detail = PostSerializer(source="lost_post", read_only=True)

    class Meta(ClaimSerializer.Meta):
        fields = ClaimSerializer.Meta.fields + (
            "claimant_username", "claimant_name", "claimant_phone", "moderator_name",
            "found_post_detail", "lost_post_detail",
        )

    def get_claimant_name(self, obj):
        return obj.claimant.get_full_name() or obj.claimant.username

    def get_moderator_name(self, obj):
        return obj.moderator.username if obj.moderator else None


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
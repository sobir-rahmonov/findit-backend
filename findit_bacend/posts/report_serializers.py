from rest_framework import serializers

from accounts.models import User

from .models import Post, Report


class ReportSerializer(serializers.ModelSerializer):
    post_title = serializers.SerializerMethodField()
    target_username = serializers.SerializerMethodField()
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = (
            "id", "post", "post_title", "target_user", "target_username",
            "reason", "reason_display", "text",
            "status", "status_display", "resolution_note", "created_at",
        )
        read_only_fields = ("status", "resolution_note", "created_at")
        extra_kwargs = {
            "post": {"required": False, "allow_null": True},
            "target_user": {"required": False, "allow_null": True},
        }

    def get_post_title(self, obj):
        return obj.post.title if obj.post else None

    def get_target_username(self, obj):
        return obj.target_user.username if obj.target_user else None

    def validate(self, attrs):
        user = self.context["request"].user
        post = attrs.get("post")
        target = attrs.get("target_user")

        if bool(post) == bool(target):
            raise serializers.ValidationError(
                "Bitta e'lon yoki bitta foydalanuvchini ko'rsating (ikkalasini emas)."
            )

        if post:
            if post.author_id == user.id:
                raise serializers.ValidationError("O'z e'loningizga shikoyat qila olmaysiz.")
            if post.status not in (Post.Status.ACTIVE, Post.Status.HANDOVER):
                raise serializers.ValidationError("Bu e'longa shikoyat yuborib bo'lmaydi.")
        else:
            if target.id == user.id:
                raise serializers.ValidationError("O'zingizga shikoyat qila olmaysiz.")

        if attrs.get("reason") == "other" and len((attrs.get("text") or "").strip()) < 5:
            raise serializers.ValidationError(
                {"text": "«Boshqa» sababi uchun izohni yozing."}
            )

        if Report.objects.filter(
            reporter=user, status=Report.Status.OPEN, post=post, target_user=target
        ).exists():
            raise serializers.ValidationError(
                "Bu bo'yicha shikoyatingiz allaqachon ko'rib chiqilmoqda."
            )
        return attrs


class ModerationReportSerializer(ReportSerializer):
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)
    handled_by_name = serializers.SerializerMethodField()
    post_info = serializers.SerializerMethodField()
    target_info = serializers.SerializerMethodField()

    class Meta(ReportSerializer.Meta):
        fields = ReportSerializer.Meta.fields + (
            "reporter_username", "handled_by_name", "handled_at",
            "post_info", "target_info",
        )

    def get_handled_by_name(self, obj):
        return obj.handled_by.username if obj.handled_by else None

    def get_post_info(self, obj):
        p = obj.post
        if not p:
            return None
        return {
            "id": p.id,
            "title": p.title,
            "type": p.type,
            "status": p.status,
            "author_id": p.author_id,
            "author_username": p.author.username,
        }

    def get_target_info(self, obj):
        u = obj.target_user
        if not u:
            return None
        return {"id": u.id, "username": u.username, "is_blocked": u.is_blocked}


class ReportActionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=255)
    reject_post = serializers.BooleanField(required=False, default=False)
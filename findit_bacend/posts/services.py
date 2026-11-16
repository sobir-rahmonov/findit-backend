from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.models import Notification
from notifications.services import notify

from .matching import run_matching
from .models import Match, Post


@transaction.atomic
def approve_post(post, moderator):
    if post.status != Post.Status.PENDING:
        raise ValidationError("Faqat tekshiruvdagi e'lonni tasdiqlash mumkin.")

    post.status = Post.Status.ACTIVE
    post.reject_reason = ""
    post.moderated_by = moderator
    post.moderated_at = timezone.now()
    post.save(update_fields=["status", "reject_reason", "moderated_by", "moderated_at", "updated_at"])

    notify(
        post.author,
        Notification.Kind.POST_APPROVED,
        "E'loningiz tasdiqlandi",
        f"«{post.title}» e'loni faollashtirildi.",
        post=post,
    )
    run_matching(post)
    return post


@transaction.atomic
def reject_post(post, moderator, reason):
    from claims.models import Claim

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Rad etish sababini yozing.")
    if post.status not in (Post.Status.PENDING, Post.Status.ACTIVE):
        raise ValidationError("Bu e'lonni rad etib bo'lmaydi.")

    now = timezone.now()
    post.status = Post.Status.REJECTED
    post.reject_reason = reason[:255]
    post.moderated_by = moderator
    post.moderated_at = now
    post.save(update_fields=["status", "reject_reason", "moderated_by", "moderated_at", "updated_at"])

    # Eskirgan mosliklar o'chiriladi
    Match.objects.filter(Q(lost_post=post) | Q(found_post=post)).delete()

    # E'longa kutilayotgan da'volar bekor qilinadi
    pending_claims = Claim.objects.filter(
        found_post=post, status=Claim.Status.PENDING
    ).select_related("claimant")
    for claim in pending_claims:
        claim.status = Claim.Status.CANCELLED
        claim.moderator = moderator
        claim.moderator_note = "E'lon rad etilgani sababli da'vo bekor qilindi."
        claim.reviewed_at = now
        claim.save()
        notify(
            claim.claimant,
            Notification.Kind.CLAIM_REJECTED,
            "Da'vo bekor qilindi",
            claim.moderator_note,
            post=post,
            claim=claim,
        )

    notify(
        post.author,
        Notification.Kind.POST_REJECTED,
        "E'loningiz rad etildi",
        f"«{post.title}»: {post.reject_reason}",
        post=post,
    )
    return post
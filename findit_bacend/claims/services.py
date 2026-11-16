from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.models import Notification
from notifications.services import notify
from posts.models import Post

from .models import Claim


def _require_reason(reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Sababni yozing.")
    return reason[:255]


@transaction.atomic
def approve_claim(claim, moderator, note=""):
    if claim.status != Claim.Status.PENDING:
        raise ValidationError("Faqat ko'rib chiqilayotgan da'voni tasdiqlash mumkin.")
    if claim.claimant_id == moderator.id:
        raise ValidationError("O'z da'vongizni o'zingiz tasdiqlay olmaysiz.")

    found = claim.found_post
    if found.status != Post.Status.ACTIVE:
        raise ValidationError("Topilgan e'lon faol emas.")

    now = timezone.now()
    claim.status = Claim.Status.APPROVED
    claim.moderator = moderator
    claim.moderator_note = (note or "")[:255]
    claim.reviewed_at = now
    claim.save()

    found.status = Post.Status.HANDOVER
    found.save(update_fields=["status", "updated_at"])

    lost = claim.lost_post
    if lost and lost.status == Post.Status.ACTIVE:
        lost.status = Post.Status.HANDOVER
        lost.save(update_fields=["status", "updated_at"])

    # Shu buyumga boshqa kutilayotgan da'volar bekor qilinadi
    others = Claim.objects.filter(found_post=found, status=Claim.Status.PENDING).exclude(
        pk=claim.pk
    ).select_related("claimant")
    for other in others:
        other.status = Claim.Status.CANCELLED
        other.moderator = moderator
        other.moderator_note = "Bu buyum uchun boshqa da'vo tasdiqlandi."
        other.reviewed_at = now
        other.save()
        notify(
            other.claimant,
            Notification.Kind.CLAIM_REJECTED,
            "Da'vo bekor qilindi",
            other.moderator_note,
            post=found,
            claim=other,
        )

    pickup = found.storage_note or "Moderator siz bilan bog'lanadi."
    notify(
        claim.claimant,
        Notification.Kind.CLAIM_APPROVED,
        "Da'voyingiz tasdiqlandi",
        f"«{found.title}» egasi sifatida tasdiqlandingiz. Buyumni olish: {pickup}",
        post=found,
        claim=claim,
    )
    notify(
        found.author,
        Notification.Kind.CLAIM_APPROVED,
        "Buyum egasi aniqlandi",
        f"«{found.title}» uchun egasi tasdiqlandi. Topshirish jarayoni boshlandi.",
        post=found,
    )
    return claim


@transaction.atomic
def reject_claim(claim, moderator, reason):
    if claim.status != Claim.Status.PENDING:
        raise ValidationError("Faqat ko'rib chiqilayotgan da'voni rad etish mumkin.")
    reason = _require_reason(reason)

    claim.status = Claim.Status.REJECTED
    claim.moderator = moderator
    claim.moderator_note = reason
    claim.reviewed_at = timezone.now()
    claim.save()

    notify(
        claim.claimant,
        Notification.Kind.CLAIM_REJECTED,
        "Da'voyingiz rad etildi",
        f"«{claim.found_post.title}»: {reason}",
        post=claim.found_post,
        claim=claim,
    )
    return claim


@transaction.atomic
def complete_claim(claim, moderator, note=""):
    if claim.status != Claim.Status.APPROVED:
        raise ValidationError("Faqat tasdiqlangan da'voni topshirilgan deb belgilash mumkin.")

    now = timezone.now()
    claim.status = Claim.Status.COMPLETED
    claim.handover_note = (note or "")[:255]
    claim.handed_over_at = now
    claim.save()

    for post in (claim.found_post, claim.lost_post):
        if post and post.status == Post.Status.HANDOVER:
            post.status = Post.Status.CLOSED
            post.closed_at = now
            post.save(update_fields=["status", "closed_at", "updated_at"])

    found = claim.found_post
    notify(
        claim.claimant,
        Notification.Kind.HANDOVER_COMPLETED,
        "Buyum topshirildi",
        f"«{found.title}» sizga topshirildi. Yaxshi kun tilaymiz!",
        post=found,
        claim=claim,
    )
    notify(
        found.author,
        Notification.Kind.HANDOVER_COMPLETED,
        "Buyum egasiga qaytarildi",
        f"«{found.title}» egasiga topshirildi. Yordamingiz uchun rahmat!",
        post=found,
    )
    return claim


@transaction.atomic
def revoke_claim(claim, moderator, reason):
    """Tasdiqlangan, lekin hali topshirilmagan da'voni bekor qilish."""
    if claim.status != Claim.Status.APPROVED:
        raise ValidationError("Faqat tasdiqlangan da'voni bekor qilish mumkin.")
    reason = _require_reason(reason)

    claim.status = Claim.Status.CANCELLED
    claim.moderator = moderator
    claim.moderator_note = reason
    claim.save()

    for post in (claim.found_post, claim.lost_post):
        if post and post.status == Post.Status.HANDOVER:
            post.status = Post.Status.ACTIVE
            post.save(update_fields=["status", "updated_at"])

    notify(
        claim.claimant,
        Notification.Kind.CLAIM_REJECTED,
        "Tasdiq bekor qilindi",
        f"«{claim.found_post.title}»: {reason}",
        post=claim.found_post,
        claim=claim,
    )
    notify(
        claim.found_post.author,
        Notification.Kind.SYSTEM,
        "Topshirish bekor qilindi",
        f"«{claim.found_post.title}» e'loni yana faol.",
        post=claim.found_post,
    )
    return claim


def cancel_claim(claim):
    """Da'vogarning o'zi kutilayotgan da'voni bekor qiladi."""
    if claim.status != Claim.Status.PENDING:
        raise ValidationError("Faqat ko'rib chiqilayotgan da'voni bekor qilish mumkin.")
    claim.status = Claim.Status.CANCELLED
    claim.save()
    return claim
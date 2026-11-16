from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.models import Notification
from notifications.services import notify

from .models import Post, Report
from .services import reject_post


def _finish(report, moderator, status, note):
    report.status = status
    report.handled_by = moderator
    report.handled_at = timezone.now()
    report.resolution_note = note
    report.save()


@transaction.atomic
def resolve_report(report, moderator, note, reject_post_too=False):
    """Shikoyat o'rinli. Ixtiyoriy: e'lonni shu zahoti rad etish."""
    if report.status != Report.Status.OPEN:
        raise ValidationError("Bu shikoyat allaqachon ko'rib chiqilgan.")

    if reject_post_too:
        post = report.post
        if not post:
            raise ValidationError("Bu shikoyat e'longa emas, e'lonni rad etib bo'lmaydi.")
        if post.status not in (Post.Status.PENDING, Post.Status.ACTIVE):
            raise ValidationError(
                "E'lonni rad etib bo'lmaydi (u topshirish jarayonida yoki yopilgan)."
            )
        reject_post(post, moderator, note)

    _finish(report, moderator, Report.Status.RESOLVED, note)
    notify(
        report.reporter,
        Notification.Kind.REPORT_RESOLVED,
        "Shikoyatingiz ko'rib chiqildi",
        f"Shikoyatingiz o'rinli deb topildi. {note}",
        post=report.post,
    )
    return report


@transaction.atomic
def dismiss_report(report, moderator, note):
    """Shikoyat asossiz."""
    if report.status != Report.Status.OPEN:
        raise ValidationError("Bu shikoyat allaqachon ko'rib chiqilgan.")

    _finish(report, moderator, Report.Status.DISMISSED, note)
    notify(
        report.reporter,
        Notification.Kind.REPORT_RESOLVED,
        "Shikoyatingiz ko'rib chiqildi",
        f"Shikoyat asossiz deb topildi. {note}",
        post=report.post,
    )
    return report
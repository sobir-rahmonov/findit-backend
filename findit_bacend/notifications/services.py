from .models import Notification


def notify(user, kind, title, message="", post=None, claim=None):
    """Foydalanuvchiga bildirishnoma yaratadi."""
    return Notification.objects.create(
        user=user, kind=kind, title=title, message=message, post=post, claim=claim
    )
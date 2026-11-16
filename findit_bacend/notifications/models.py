from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        POST_APPROVED = "post_approved", "E'lon tasdiqlandi"
        POST_REJECTED = "post_rejected", "E'lon rad etildi"
        MATCH_FOUND = "match_found", "Mos buyum topildi"
        CLAIM_RECEIVED = "claim_received", "Da'vo keldi"
        CLAIM_APPROVED = "claim_approved", "Da'vo tasdiqlandi"
        CLAIM_REJECTED = "claim_rejected", "Da'vo rad etildi"
        HANDOVER_COMPLETED = "handover_completed", "Buyum topshirildi"
        REPORT_RESOLVED = "report_resolved", "Shikoyat ko'rib chiqildi"
        SYSTEM = "system", "Tizim xabari"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications", verbose_name="Foydalanuvchi",
    )
    kind = models.CharField("Turi", max_length=30, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField("Sarlavha", max_length=200)
    message = models.TextField("Matn", blank=True)
    post = models.ForeignKey(
        "posts.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    claim = models.ForeignKey(
        "claims.Claim", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_read = models.BooleanField("O'qilgan", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user}: {self.title}"
from django.conf import settings
from django.db import models
from django.db.models import Q


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ko'rib chiqilmoqda"
        APPROVED = "approved", "Tasdiqlandi"
        REJECTED = "rejected", "Rad etildi"
        COMPLETED = "completed", "Topshirildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    found_post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE,
        related_name="claims", verbose_name="Topilgan e'lon",
    )
    lost_post = models.ForeignKey(
        "posts.Post", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="claims_made", verbose_name="Da'vogarning yo'qolgan e'loni",
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="claims", verbose_name="Da'vogar",
    )
    description = models.TextField(
        "Buyumni tasdiqlovchi belgilar",
        help_text="Faqat egasi biladigan belgilar: chizilgan joy, ekran rasmi, ichidagi narsalar...",
    )
    proof_image = models.ImageField("Isbot rasmi", upload_to="claims/", null=True, blank=True)

    status = models.CharField(
        "Holat", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="claims_reviewed", verbose_name="Tekshirgan moderator",
    )
    moderator_note = models.CharField("Moderator izohi", max_length=255, blank=True)
    reviewed_at = models.DateTimeField("Tekshirilgan vaqt", null=True, blank=True)

    handover_note = models.CharField("Topshirish izohi", max_length=255, blank=True)
    handed_over_at = models.DateTimeField("Topshirilgan vaqt", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Da'vo"
        verbose_name_plural = "Da'volar"
        ordering = ["-created_at"]
        constraints = [
            # bitta odam bitta buyumga bir vaqtda faqat bitta ochiq da'vo yubora oladi
            models.UniqueConstraint(
                fields=["found_post", "claimant"],
                condition=Q(status="pending"),
                name="unique_pending_claim",
            )
        ]

    def __str__(self):
        return f"Da'vo #{self.pk}: {self.claimant} → {self.found_post_id}"
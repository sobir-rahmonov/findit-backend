from django.core.validators import MaxValueValidator
from django.db import models


class SystemSettings(models.Model):
    require_moderation = models.BooleanField(
        "E'lonlar moderator tekshiruvidan o'tsin", default=True
    )
    match_threshold = models.PositiveSmallIntegerField(
        "Moslik chegarasi (0-100)", default=50, validators=[MaxValueValidator(100)]
    )
    match_max_distance_km = models.FloatField(
        "Moslik uchun eng katta masofa (km)", default=10
    )
    match_date_window_days = models.PositiveSmallIntegerField(
        "Moslik uchun sana farqi (kun)", default=30
    )
    max_active_posts_per_user = models.PositiveSmallIntegerField(
        "Bitta foydalanuvchining faol e'lonlari chegarasi", default=20
    )

    class Meta:
        verbose_name = "Tizim sozlamalari"
        verbose_name_plural = "Tizim sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1  # doim bitta qator
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # sozlamalarni o'chirib bo'lmaydi

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Tizim sozlamalari"
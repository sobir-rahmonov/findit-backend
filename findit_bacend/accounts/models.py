from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "user", "Foydalanuvchi"
        MODERATOR = "moderator", "Moderator"
        ADMIN = "admin", "Administrator"

    phone = models.CharField("Telefon", max_length=20, blank=True)
    role = models.CharField("Rol", max_length=20, choices=Role.choices, default=Role.USER)
    is_blocked = models.BooleanField("Bloklangan", default=False)
    blocked_reason = models.CharField("Bloklash sababi", max_length=255, blank=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def save(self, *args, **kwargs):
        # Superuser avtomatik admin bo'ladi, Django admin paneliga faqat adminlar kiradi
        if self.is_superuser:
            self.role = self.Role.ADMIN
        self.is_staff = self.is_superuser or self.role == self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN

    @property
    def is_moderator(self):
        """Moderator ishini moderator ham, admin ham qila oladi."""
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    def __str__(self):
        return self.username
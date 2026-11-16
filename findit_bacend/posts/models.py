from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField("Nomi", max_length=100, unique=True)
    slug = models.SlugField("Slug", max_length=120, unique=True)
    icon = models.CharField("Belgi nomi", max_length=40, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Place(models.Model):
    class PlaceType(models.TextChoices):
        UNIVERSITY = "university", "Universitet"
        MALL = "mall", "Savdo markazi"
        LIBRARY = "library", "Kutubxona"
        AIRPORT = "airport", "Aeroport"
        STATION = "station", "Vokzal / metro"
        OTHER = "other", "Boshqa jamoat joyi"

    name = models.CharField("Nomi", max_length=200)
    place_type = models.CharField(
        "Turi", max_length=20, choices=PlaceType.choices, default=PlaceType.OTHER
    )
    address = models.CharField("Manzil", max_length=255, blank=True)
    latitude = models.FloatField(
        "Kenglik", null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.FloatField(
        "Uzunlik", null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Joy"
        verbose_name_plural = "Joylar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Post(models.Model):
    class Type(models.TextChoices):
        LOST = "lost", "Yo'qolgan"
        FOUND = "found", "Topilgan"

    class Status(models.TextChoices):
        PENDING = "pending", "Tekshiruvda"
        ACTIVE = "active", "Faol"
        HANDOVER = "handover", "Topshirilmoqda"
        CLOSED = "closed", "Yopilgan"
        REJECTED = "rejected", "Rad etilgan"

    class Color(models.TextChoices):
        BLACK = "black", "Qora"
        WHITE = "white", "Oq"
        GRAY = "gray", "Kulrang"
        RED = "red", "Qizil"
        BLUE = "blue", "Ko'k"
        GREEN = "green", "Yashil"
        YELLOW = "yellow", "Sariq"
        ORANGE = "orange", "To'q sariq"
        PURPLE = "purple", "Binafsha"
        PINK = "pink", "Pushti"
        BROWN = "brown", "Jigarrang"
        SILVER = "silver", "Kumush"
        GOLD = "gold", "Oltin"
        OTHER = "other", "Boshqa"

    type = models.CharField("Turi", max_length=10, choices=Type.choices)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="posts", verbose_name="Muallif",
    )
    title = models.CharField("Buyum nomi", max_length=200)
    description = models.TextField("Tavsif", blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="posts", verbose_name="Kategoriya"
    )
    color = models.CharField("Rangi", max_length=20, choices=Color.choices, default=Color.OTHER)
    brand = models.CharField("Brend / model", max_length=100, blank=True)

    place = models.ForeignKey(
        Place, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="posts", verbose_name="Joy",
    )
    location_detail = models.CharField("Aniq joy", max_length=255, blank=True)
    latitude = models.FloatField(
        "Kenglik", null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.FloatField(
        "Uzunlik", null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    event_date = models.DateField("Yo'qolgan / topilgan sana")
    image = models.ImageField("Rasm", upload_to="posts/", null=True, blank=True)

    # Faqat topilgan buyumlar uchun
    storage_note = models.CharField(
        "Buyum qayerda saqlanmoqda", max_length=255, blank=True
    )
    private_detail = models.TextField(
        "Yashirin belgi (faqat egasi biladi)", blank=True,
        help_text="Jamoatga ko'rsatilmaydi. Egalikni tekshirish uchun.",
    )

    status = models.CharField(
        "Holat", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reject_reason = models.CharField("Rad etish sababi", max_length=255, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="moderated_posts", verbose_name="Tekshirgan moderator",
    )
    moderated_at = models.DateTimeField("Tekshirilgan vaqt", null=True, blank=True)
    closed_at = models.DateTimeField("Yopilgan vaqt", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None


class Match(models.Model):
    lost_post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="matches_as_lost",
        verbose_name="Yo'qolgan e'lon",
    )
    found_post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="matches_as_found",
        verbose_name="Topilgan e'lon",
    )
    score = models.PositiveSmallIntegerField("Moslik balli (0-100)")
    reasons = models.JSONField("Ball tafsilotlari", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Moslik"
        verbose_name_plural = "Mosliklar"
        ordering = ["-score", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lost_post", "found_post"], name="unique_match_pair"
            )
        ]

    def __str__(self):
        return f"{self.lost_post_id} ↔ {self.found_post_id} ({self.score}%)"


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        FAKE = "fake", "Soxta e'lon"
        INAPPROPRIATE = "inappropriate", "Nomaqbul mazmun"
        FRAUD = "fraud", "Firibgarlik"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        OPEN = "open", "Ko'rib chiqilmagan"
        RESOLVED = "resolved", "Hal qilindi"
        DISMISSED = "dismissed", "Asossiz"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="reports_made", verbose_name="Shikoyat qilgan",
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True,
        related_name="reports", verbose_name="E'lon",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="reports_received", verbose_name="Foydalanuvchi",
    )
    reason = models.CharField("Sabab", max_length=20, choices=Reason.choices)
    text = models.TextField("Izoh", blank=True)
    status = models.CharField(
        "Holat", max_length=20, choices=Status.choices, default=Status.OPEN
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reports_handled", verbose_name="Ko'rib chiqqan",
    )
    resolution_note = models.CharField("Qaror izohi", max_length=255, blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shikoyat"
        verbose_name_plural = "Shikoyatlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Shikoyat #{self.pk}: {self.get_reason_display()}"
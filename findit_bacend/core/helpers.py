from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import User
from core.models import SystemSettings
from notifications.models import Notification
from posts.models import Category, Post

PASSWORD = "Sinov12345"


class FindItTestCase(APITestCase):
    """Barcha testlar uchun umumiy asos: 4 ta foydalanuvchi va bitta kategoriya."""

    def setUp(self):
        self.category = Category.objects.create(name="Elektronika", slug="elektronika")
        self.ali = self.make_user("ali")
        self.vali = self.make_user("vali")
        self.moder = self.make_user("moder", role=User.Role.MODERATOR)
        self.admin = self.make_user("boss", role=User.Role.ADMIN)

    # ---------- yordamchilar ----------
    def make_user(self, username, role=User.Role.USER, **extra):
        return User.objects.create_user(
            username=username, password=PASSWORD, role=role, **extra
        )

    def login_as(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token

    def anonymous(self):
        self.client.credentials()

    def make_post(self, author, type=Post.Type.LOST, status=Post.Status.ACTIVE, **extra):
        data = {
            "type": type,
            "author": author,
            "title": "Qora AirPods",
            "color": "black",
            "category": self.category,
            "event_date": timezone.localdate(),
            "status": status,
        }
        data.update(extra)
        return Post.objects.create(**data)

    def post_payload(self, **extra):
        data = {
            "type": "lost",
            "title": "Qora AirPods",
            "category": self.category.id,
            "color": "black",
            "event_date": timezone.localdate().isoformat(),
        }
        data.update(extra)
        return data

    def set_settings(self, **kwargs):
        config = SystemSettings.load()
        for key, value in kwargs.items():
            setattr(config, key, value)
        config.save()

    def kinds(self, user):
        """Foydalanuvchi olgan bildirishnoma turlari."""
        return list(Notification.objects.filter(user=user).values_list("kind", flat=True))

    def api_post(self, url, data=None):
        return self.client.post(url, data or {}, format="json")
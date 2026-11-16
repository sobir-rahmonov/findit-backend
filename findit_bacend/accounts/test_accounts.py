from rest_framework.authtoken.models import Token

from accounts.models import User
from core.helpers import PASSWORD, FindItTestCase


class RegisterLoginTests(FindItTestCase):
    def test_register_creates_user_and_returns_token(self):
        res = self.api_post("/api/auth/register/", {"username": "new", "password": PASSWORD})
        self.assertEqual(res.status_code, 201)
        self.assertIn("token", res.data)
        self.assertEqual(User.objects.get(username="new").role, User.Role.USER)

    def test_register_cannot_choose_role(self):
        res = self.api_post(
            "/api/auth/register/", {"username": "sneaky", "password": PASSWORD, "role": "admin"}
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(User.objects.get(username="sneaky").role, User.Role.USER)

    def test_register_rejects_duplicate_username(self):
        res = self.api_post("/api/auth/register/", {"username": "ali", "password": PASSWORD})
        self.assertEqual(res.status_code, 400)

    def test_register_rejects_short_password(self):
        res = self.api_post("/api/auth/register/", {"username": "new", "password": "123"})
        self.assertEqual(res.status_code, 400)

    def test_login_returns_token(self):
        res = self.api_post("/api/auth/login/", {"username": "ali", "password": PASSWORD})
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)

    def test_login_wrong_password(self):
        res = self.api_post("/api/auth/login/", {"username": "ali", "password": "xato"})
        self.assertEqual(res.status_code, 400)

    def test_blocked_user_cannot_login(self):
        User.objects.filter(pk=self.ali.pk).update(is_blocked=True)
        res = self.api_post("/api/auth/login/", {"username": "ali", "password": PASSWORD})
        self.assertEqual(res.status_code, 400)
        self.assertIn("bloklangan", str(res.data))


class TokenAndProfileTests(FindItTestCase):
    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_blocked_user_token_stops_working(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        User.objects.filter(pk=self.ali.pk).update(is_blocked=True)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_me_returns_and_updates_profile(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "ali")
        res = self.client.patch("/api/auth/me/", {"phone": "+998901234567"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.ali.refresh_from_db()
        self.assertEqual(self.ali.phone, "+998901234567")

    def test_me_cannot_change_role(self):
        self.login_as(self.ali)
        self.client.patch("/api/auth/me/", {"role": "admin"}, format="json")
        self.ali.refresh_from_db()
        self.assertEqual(self.ali.role, User.Role.USER)

    def test_change_password_gives_new_token_and_revokes_old(self):
        old = self.login_as(self.ali)
        res = self.api_post(
            "/api/auth/change-password/",
            {"old_password": PASSWORD, "new_password": "Yangi12345"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old.key}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

        self.anonymous()
        res = self.api_post("/api/auth/login/", {"username": "ali", "password": "Yangi12345"})
        self.assertEqual(res.status_code, 200)

    def test_change_password_wrong_old_password(self):
        self.login_as(self.ali)
        res = self.api_post(
            "/api/auth/change-password/",
            {"old_password": "xato", "new_password": "Yangi12345"},
        )
        self.assertEqual(res.status_code, 400)

    def test_logout_deletes_token(self):
        self.login_as(self.ali)
        self.assertEqual(self.api_post("/api/auth/logout/").status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.ali).exists())
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)


class RoleModelTests(FindItTestCase):
    def test_role_properties(self):
        self.assertFalse(self.ali.is_moderator)
        self.assertFalse(self.ali.is_administrator)
        self.assertTrue(self.moder.is_moderator)
        self.assertFalse(self.moder.is_administrator)
        self.assertTrue(self.admin.is_moderator)
        self.assertTrue(self.admin.is_administrator)

    def test_only_admin_role_is_staff(self):
        self.assertFalse(self.ali.is_staff)
        self.assertFalse(self.moder.is_staff)
        self.assertTrue(self.admin.is_staff)

    def test_superuser_becomes_admin(self):
        root = User.objects.create_superuser("root", password="Sinov12345")
        self.assertEqual(root.role, User.Role.ADMIN)
        self.assertTrue(root.is_staff)
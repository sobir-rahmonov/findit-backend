from django.utils import timezone
from rest_framework.authtoken.models import Token

from accounts.models import User
from claims.models import Claim
from core.helpers import FindItTestCase
from core.models import SystemSettings
from posts.models import Match, Post, Report

USERS = "/api/admin/users/"
SETTINGS = "/api/admin/settings/"
STATS = "/api/admin/statistics/"


class AdminAccessTests(FindItTestCase):
    def test_admin_endpoints_are_admin_only(self):
        for url in (USERS, SETTINGS, STATS):
            self.anonymous()
            self.assertEqual(self.client.get(url).status_code, 401, url)
            self.login_as(self.ali)
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.login_as(self.moder)
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.login_as(self.admin)
            self.assertEqual(self.client.get(url).status_code, 200, url)


class AdminUserTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.login_as(self.admin)

    def test_list_filter_and_search(self):
        self.assertEqual(self.client.get(USERS).data["count"], 4)
        self.assertEqual(self.client.get(USERS, {"role": "moderator"}).data["count"], 1)
        self.assertEqual(self.client.get(USERS, {"search": "vali"}).data["count"], 1)

    def test_list_shows_counts(self):
        self.make_post(self.ali)
        res = self.client.get(USERS, {"search": "ali"})
        ali = next(u for u in res.data["results"] if u["username"] == "ali")
        self.assertEqual(ali["posts_count"], 1)
        self.assertEqual(ali["claims_count"], 0)

    def test_block_user_revokes_tokens(self):
        token = Token.objects.create(user=self.ali)
        res = self.api_post(f"{USERS}{self.ali.id}/block/", {"reason": "Qoidabuzarlik"})
        self.assertEqual(res.status_code, 200)

        self.ali.refresh_from_db()
        self.assertTrue(self.ali.is_blocked)
        self.assertEqual(self.ali.blocked_reason, "Qoidabuzarlik")
        self.assertFalse(Token.objects.filter(user=self.ali).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_cannot_block_self_admin_or_twice(self):
        self.assertEqual(self.api_post(f"{USERS}{self.admin.id}/block/").status_code, 400)
        other_admin = self.make_user("boss2", role=User.Role.ADMIN)
        self.assertEqual(self.api_post(f"{USERS}{other_admin.id}/block/").status_code, 400)
        self.api_post(f"{USERS}{self.ali.id}/block/")
        self.assertEqual(self.api_post(f"{USERS}{self.ali.id}/block/").status_code, 400)

    def test_unblock_user(self):
        User.objects.filter(pk=self.ali.pk).update(is_blocked=True, blocked_reason="X")
        res = self.api_post(f"{USERS}{self.ali.id}/unblock/")
        self.assertEqual(res.status_code, 200)
        self.ali.refresh_from_db()
        self.assertFalse(self.ali.is_blocked)
        self.assertEqual(self.ali.blocked_reason, "")

    def test_cannot_unblock_active_user(self):
        self.assertEqual(self.api_post(f"{USERS}{self.ali.id}/unblock/").status_code, 400)

    def test_appoint_moderator(self):
        res = self.api_post(f"{USERS}{self.ali.id}/set-role/", {"role": "moderator"})
        self.assertEqual(res.status_code, 200)
        self.ali.refresh_from_db()
        self.assertEqual(self.ali.role, User.Role.MODERATOR)
        self.assertIn("system", self.kinds(self.ali))

        self.login_as(self.ali)  # yangi moderator navbatni ocha oladi
        self.assertEqual(self.client.get("/api/moderation/posts/").status_code, 200)

    def test_remove_moderator_role(self):
        res = self.api_post(f"{USERS}{self.moder.id}/set-role/", {"role": "user"})
        self.assertEqual(res.status_code, 200)
        self.login_as(self.moder)
        self.assertEqual(self.client.get("/api/moderation/posts/").status_code, 403)

    def test_role_change_rules(self):
        # admin roliga API orqali tayinlab bo'lmaydi
        self.assertEqual(self.api_post(f"{USERS}{self.ali.id}/set-role/", {"role": "admin"}).status_code, 400)
        # o'z rolini va administrator rolini o'zgartirib bo'lmaydi
        self.assertEqual(self.api_post(f"{USERS}{self.admin.id}/set-role/", {"role": "user"}).status_code, 400)
        # bir xil rol
        self.assertEqual(self.api_post(f"{USERS}{self.ali.id}/set-role/", {"role": "user"}).status_code, 400)


class SystemSettingsTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.login_as(self.admin)

    def test_get_settings(self):
        res = self.client.get(SETTINGS)
        self.assertEqual(res.data["match_threshold"], 50)
        self.assertTrue(res.data["require_moderation"])

    def test_patch_settings(self):
        res = self.client.patch(
            SETTINGS, {"match_threshold": 40, "max_active_posts_per_user": 5}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        config = SystemSettings.load()
        self.assertEqual((config.match_threshold, config.max_active_posts_per_user), (40, 5))

    def test_invalid_values_rejected(self):
        for bad in ({"match_threshold": 150}, {"match_threshold": 0},
                    {"match_max_distance_km": 0}, {"max_active_posts_per_user": 0}):
            res = self.client.patch(SETTINGS, bad, format="json")
            self.assertEqual(res.status_code, 400, bad)
        self.assertEqual(SystemSettings.load().match_threshold, 50)

    def test_user_cannot_change_settings(self):
        self.login_as(self.ali)
        res = self.client.patch(SETTINGS, {"match_threshold": 10}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_settings_change_affects_new_posts(self):
        self.client.patch(SETTINGS, {"require_moderation": False}, format="json")
        self.login_as(self.ali)
        res = self.api_post("/api/posts/", self.post_payload())
        self.assertEqual(res.data["status"], "active")


class StatisticsTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.lost = self.make_post(self.ali, Post.Type.LOST)
        self.found = self.make_post(self.vali, Post.Type.FOUND)
        self.make_post(self.ali, Post.Type.LOST, status=Post.Status.PENDING)
        self.login_as(self.admin)

    def test_structure_and_counts(self):
        data = self.client.get(STATS).data
        self.assertEqual(data["users"]["total"], 4)
        self.assertEqual(data["users"]["by_role"], {"user": 2, "moderator": 1, "admin": 1})
        self.assertEqual(data["posts"]["total"], 3)
        self.assertEqual(data["posts"]["by_status"]["active"], 2)
        self.assertEqual(data["posts"]["by_status"]["pending"], 1)
        self.assertEqual(data["posts"]["by_type"], {"lost": 2, "found": 1})
        self.assertEqual(data["posts"]["top_categories"], [{"name": "Elektronika", "count": 3}])
        self.assertEqual(data["queues"]["pending_posts"], 1)
        self.assertEqual(data["queues"]["pending_claims"], 0)
        self.assertEqual(data["queues"]["open_reports"], 0)

    def test_daily_trend_covers_14_days(self):
        trend = self.client.get(STATS).data["posts"]["per_day"]
        self.assertEqual(len(trend), 14)
        today = trend[-1]
        self.assertEqual(today["date"], timezone.localdate().isoformat())
        self.assertEqual((today["lost"], today["found"]), (2, 1))

    def test_return_rate(self):
        data = self.client.get(STATS).data
        self.assertEqual(data["returns"]["returned_items"], 0)
        self.assertEqual(data["returns"]["return_rate_percent"], 0)

        Claim.objects.create(
            found_post=self.found, claimant=self.ali, description="Belgilar",
            status=Claim.Status.COMPLETED,
        )
        data = self.client.get(STATS).data
        self.assertEqual(data["returns"]["returned_items"], 1)
        self.assertEqual(data["returns"]["found_items_total"], 1)
        self.assertEqual(data["returns"]["return_rate_percent"], 100.0)

    def test_claims_reports_and_matches_counts(self):
        Claim.objects.create(found_post=self.found, claimant=self.ali, description="Belgilar")
        Report.objects.create(reporter=self.ali, target_user=self.vali, reason="spam")
        Match.objects.create(lost_post=self.lost, found_post=self.found, score=80)
        data = self.client.get(STATS).data
        self.assertEqual(data["claims"]["by_status"]["pending"], 1)
        self.assertEqual(data["reports"]["by_status"]["open"], 1)
        self.assertEqual(data["matches"]["total"], 1)
        self.assertEqual(data["queues"]["pending_claims"], 1)
        self.assertEqual(data["queues"]["open_reports"], 1)
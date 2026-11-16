from datetime import timedelta

from django.utils import timezone

from core.helpers import FindItTestCase
from core.models import SystemSettings
from notifications.models import Notification
from posts import matching
from posts.matching import run_matching
from posts.models import Category, Match, Place, Post

TOSHKENT = (41.2995, 69.2401)
SAMARQAND = (39.6270, 66.9750)


class ScoringFunctionTests(FindItTestCase):
    """Ball hisoblash funksiyalari (bazaga yozmasdan)."""

    def setUp(self):
        super().setUp()
        self.config = SystemSettings.load()
        self.today = timezone.localdate()

    def test_haversine_distance(self):
        d = matching.haversine_km(*TOSHKENT, *SAMARQAND)
        self.assertTrue(250 < d < 290, d)
        self.assertAlmostEqual(matching.haversine_km(*TOSHKENT, *TOSHKENT), 0, places=3)

    def test_color_points(self):
        self.assertEqual(matching.color_points("black", "black"), 20)
        self.assertEqual(matching.color_points("other", "other"), 10)
        self.assertEqual(matching.color_points("black", "other"), 8)
        self.assertEqual(matching.color_points("black", "white"), 0)

    def test_brand_points(self):
        self.assertEqual(matching.brand_points("Apple AirPods", "airpods"), 15)
        self.assertEqual(matching.brand_points("Apple", "Samsung"), 0)
        self.assertEqual(matching.brand_points("", "Apple"), 0)

    def test_text_points(self):
        lost = Post(title="Qora AirPods quloqchin", description="")
        found = Post(title="Qora AirPods topildi quloqchin", description="")
        self.assertEqual(matching.text_points(lost, found), 30)
        other = Post(title="Yashil ryukzak", description="")
        self.assertEqual(matching.text_points(lost, other), 0)

    def test_date_points(self):
        lost = Post(event_date=self.today)
        same_day = Post(event_date=self.today)
        two_days_later = Post(event_date=self.today + timedelta(days=2))
        too_late = Post(event_date=self.today + timedelta(days=40))
        before_loss = Post(event_date=self.today - timedelta(days=2))
        self.assertEqual(matching.date_points(lost, same_day, self.config), 15)
        self.assertEqual(matching.date_points(lost, two_days_later, self.config), 9)
        self.assertIsNone(matching.date_points(lost, too_late, self.config))
        self.assertIsNone(matching.date_points(lost, before_loss, self.config))

    def test_same_place_gives_full_location_points(self):
        place = Place.objects.create(name="Kutubxona")
        lost, found = Post(place=place), Post(place=place)
        points, distance = matching.location_points(lost, found, self.config)
        self.assertEqual(points, 20)
        self.assertIsNone(distance)

    def test_too_far_posts_do_not_match(self):
        lost = Post(latitude=TOSHKENT[0], longitude=TOSHKENT[1], event_date=self.today)
        found = Post(latitude=SAMARQAND[0], longitude=SAMARQAND[1], event_date=self.today)
        self.assertIsNone(matching.location_points(lost, found, self.config))
        self.assertIsNone(matching.compute_score(lost, found, self.config))


class RunMatchingTests(FindItTestCase):
    def pair(self, **found_extra):
        lost = self.make_post(self.ali, Post.Type.LOST, title="Qora AirPods quloqchin")
        found = self.make_post(
            self.vali, Post.Type.FOUND, title="Qora AirPods topildi quloqchin", **found_extra
        )
        return lost, found

    def test_creates_match_and_notifies_both_owners(self):
        lost, found = self.pair()
        created = run_matching(found)
        self.assertEqual(len(created), 1)

        match = Match.objects.get()
        self.assertEqual((match.lost_post, match.found_post), (lost, found))
        self.assertEqual(match.score, 65)  # rang 20 + sana 15 + matn 30
        self.assertIn("match_found", self.kinds(self.ali))
        self.assertIn("match_found", self.kinds(self.vali))

    def test_matching_works_from_either_side(self):
        lost, found = self.pair()
        run_matching(lost)
        self.assertEqual(Match.objects.count(), 1)

    def test_same_author_is_not_matched(self):
        self.make_post(self.ali, Post.Type.LOST)
        found = self.make_post(self.ali, Post.Type.FOUND)
        self.assertEqual(run_matching(found), [])

    def test_different_category_is_not_matched(self):
        other = Category.objects.create(name="Hujjat", slug="hujjat")
        lost, found = self.pair(category=other)
        self.assertEqual(run_matching(found), [])

    def test_low_score_is_not_matched(self):
        lost = self.make_post(self.ali, Post.Type.LOST, title="Qora AirPods")
        found = self.make_post(
            self.vali, Post.Type.FOUND, title="Yashil ryukzak", color="white"
        )
        self.assertEqual(run_matching(found), [])

    def test_only_active_posts_are_matched(self):
        lost, found = self.pair(status=Post.Status.PENDING)
        self.assertEqual(run_matching(lost), [])

    def test_threshold_setting_is_respected(self):
        lost, found = self.pair()
        self.set_settings(match_threshold=70)
        self.assertEqual(run_matching(found), [])

    def test_rerun_does_not_duplicate_matches_or_notifications(self):
        lost, found = self.pair()
        run_matching(found)
        self.assertEqual(run_matching(found), [])
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(kind="match_found").count(), 2)

    def test_stale_match_is_removed_when_post_changes(self):
        lost, found = self.pair()
        run_matching(found)
        found.color = "white"
        found.title = "Boshqa narsa"
        found.save()
        run_matching(found)
        self.assertEqual(Match.objects.count(), 0)


class MatchesEndpointTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.lost = self.make_post(self.ali, Post.Type.LOST, title="Qora AirPods quloqchin")
        self.found = self.make_post(
            self.vali, Post.Type.FOUND, title="Qora AirPods topildi quloqchin"
        )
        run_matching(self.found)
        self.url = f"/api/posts/{self.lost.id}/matches/"

    def test_author_sees_matches(self):
        self.login_as(self.ali)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["score"], 65)
        self.assertEqual(res.data["results"][0]["post"]["id"], self.found.id)

    def test_moderator_sees_matches(self):
        self.login_as(self.moder)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_stranger_cannot_see_matches(self):
        self.login_as(self.vali)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_matches_require_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
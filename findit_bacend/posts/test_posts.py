from datetime import timedelta

from django.utils import timezone

from core.helpers import FindItTestCase
from posts.models import Category, Place, Post

URL = "/api/posts/"


class PostCreateTests(FindItTestCase):
    def test_create_requires_login(self):
        self.assertEqual(self.api_post(URL, self.post_payload()).status_code, 401)

    def test_new_post_goes_to_moderation(self):
        self.login_as(self.ali)
        res = self.api_post(URL, self.post_payload())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")
        self.assertEqual(Post.objects.get(pk=res.data["id"]).author, self.ali)

    def test_post_is_active_when_moderation_is_off(self):
        self.set_settings(require_moderation=False)
        self.login_as(self.ali)
        res = self.api_post(URL, self.post_payload())
        self.assertEqual(res.data["status"], "active")

    def test_future_date_rejected(self):
        self.login_as(self.ali)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        res = self.api_post(URL, self.post_payload(event_date=tomorrow))
        self.assertEqual(res.status_code, 400)

    def test_inactive_category_rejected(self):
        self.category.is_active = False
        self.category.save()
        self.login_as(self.ali)
        self.assertEqual(self.api_post(URL, self.post_payload()).status_code, 400)

    def test_coordinates_must_be_paired(self):
        self.login_as(self.ali)
        res = self.api_post(URL, self.post_payload(latitude=41.3))
        self.assertEqual(res.status_code, 400)

    def test_coordinates_are_taken_from_place(self):
        place = Place.objects.create(name="Kutubxona", latitude=41.3, longitude=69.2)
        self.login_as(self.ali)
        res = self.api_post(URL, self.post_payload(place=place.id))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["latitude"], 41.3)
        self.assertEqual(res.data["longitude"], 69.2)

    def test_open_posts_limit(self):
        self.set_settings(max_active_posts_per_user=1)
        self.login_as(self.ali)
        self.assertEqual(self.api_post(URL, self.post_payload()).status_code, 201)
        self.assertEqual(self.api_post(URL, self.post_payload()).status_code, 400)


class PostVisibilityTests(FindItTestCase):
    def test_public_list_shows_only_active_posts(self):
        self.make_post(self.ali)
        self.make_post(self.ali, status=Post.Status.PENDING)
        self.make_post(self.ali, status=Post.Status.REJECTED)
        self.anonymous()
        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)

    def test_pending_post_visible_only_to_author_and_moderators(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        url = f"{URL}{post.id}/"
        self.anonymous()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login_as(self.vali)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login_as(self.ali)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login_as(self.moder)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_private_detail_is_hidden_from_strangers(self):
        post = self.make_post(
            self.vali, Post.Type.FOUND, private_detail="Chizilgan joy bor"
        )
        url = f"{URL}{post.id}/"

        self.login_as(self.ali)  # begona
        self.assertNotIn("private_detail", self.client.get(url).data)
        self.anonymous()
        self.assertNotIn("private_detail", self.client.get(url).data)

        self.login_as(self.vali)  # muallif
        self.assertEqual(self.client.get(url).data["private_detail"], "Chizilgan joy bor")
        self.login_as(self.moder)  # moderator
        self.assertEqual(self.client.get(url).data["private_detail"], "Chizilgan joy bor")

    def test_mine_returns_only_own_posts_in_any_status(self):
        self.make_post(self.ali)
        self.make_post(self.ali, status=Post.Status.PENDING)
        self.make_post(self.vali)
        self.login_as(self.ali)
        res = self.client.get(f"{URL}mine/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)

    def test_mine_requires_login(self):
        self.assertEqual(self.client.get(f"{URL}mine/").status_code, 401)


class PostEditDeleteTests(FindItTestCase):
    def test_editing_sends_post_back_to_moderation(self):
        post = self.make_post(self.ali)
        self.login_as(self.ali)
        res = self.client.patch(f"{URL}{post.id}/", {"title": "Yangi nom"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "pending")

    def test_only_author_can_edit(self):
        post = self.make_post(self.ali)
        self.login_as(self.vali)
        res = self.client.patch(f"{URL}{post.id}/", {"title": "Hack"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_post_type_cannot_be_changed(self):
        post = self.make_post(self.ali)
        self.login_as(self.ali)
        res = self.client.patch(f"{URL}{post.id}/", {"type": "found"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_handover_post_cannot_be_edited(self):
        post = self.make_post(self.ali, status=Post.Status.HANDOVER)
        self.login_as(self.ali)
        res = self.client.patch(f"{URL}{post.id}/", {"title": "Yangi"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_author_can_delete_own_post(self):
        post = self.make_post(self.ali)
        self.login_as(self.ali)
        self.assertEqual(self.client.delete(f"{URL}{post.id}/").status_code, 204)
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_stranger_cannot_delete_post(self):
        post = self.make_post(self.ali)
        self.login_as(self.vali)
        self.assertEqual(self.client.delete(f"{URL}{post.id}/").status_code, 403)

    def test_admin_can_delete_any_post(self):
        post = self.make_post(self.ali)
        self.login_as(self.admin)
        self.assertEqual(self.client.delete(f"{URL}{post.id}/").status_code, 204)

    def test_author_cannot_delete_closed_post(self):
        post = self.make_post(self.ali, status=Post.Status.CLOSED)
        self.login_as(self.ali)
        self.assertEqual(self.client.delete(f"{URL}{post.id}/").status_code, 403)


class PostFilterTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.docs = Category.objects.create(name="Hujjatlar", slug="hujjatlar")
        self.phone = self.make_post(self.ali, title="Qora AirPods", latitude=41.2995, longitude=69.2401)
        self.passport = self.make_post(
            self.vali, Post.Type.FOUND, title="Yashil pasport", category=self.docs,
            color="green", latitude=39.6270, longitude=66.9750,
            event_date=timezone.localdate() - timedelta(days=10),
        )

    def ids(self, **params):
        res = self.client.get(URL, params)
        self.assertEqual(res.status_code, 200)
        return {item["id"] for item in res.data["results"]}

    def test_filter_by_type(self):
        self.assertEqual(self.ids(type="found"), {self.passport.id})

    def test_filter_by_category_slug(self):
        self.assertEqual(self.ids(category="hujjatlar"), {self.passport.id})

    def test_filter_by_color(self):
        self.assertEqual(self.ids(color="black"), {self.phone.id})

    def test_search_by_title(self):
        self.assertEqual(self.ids(search="airpods"), {self.phone.id})

    def test_filter_by_date_range(self):
        week_ago = (timezone.localdate() - timedelta(days=7)).isoformat()
        self.assertEqual(self.ids(date_from=week_ago), {self.phone.id})

    def test_filter_by_map_radius(self):
        # Toshkent atrofida 10 km: Samarqanddagi e'lon kirmaydi
        self.assertEqual(self.ids(lat=41.3, lng=69.24, radius_km=10), {self.phone.id})
        # Katta radiusda ikkalasi ham
        self.assertEqual(
            self.ids(lat=41.3, lng=69.24, radius_km=500), {self.phone.id, self.passport.id}
        )
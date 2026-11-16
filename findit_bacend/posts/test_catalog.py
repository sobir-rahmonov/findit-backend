from core.helpers import FindItTestCase
from posts.models import Category, Place


class CategoryTests(FindItTestCase):
    def test_anyone_can_list_categories(self):
        res = self.client.get("/api/categories/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_inactive_category_hidden_from_users_but_visible_to_admin(self):
        Category.objects.create(name="Eski", slug="eski", is_active=False)
        self.assertEqual(len(self.client.get("/api/categories/").data), 1)
        self.login_as(self.admin)
        self.assertEqual(len(self.client.get("/api/categories/").data), 2)

    def test_only_admin_can_create_category(self):
        payload = {"name": "Hujjatlar", "slug": "hujjatlar"}
        self.login_as(self.ali)
        self.assertEqual(self.api_post("/api/categories/", payload).status_code, 403)
        self.login_as(self.admin)
        self.assertEqual(self.api_post("/api/categories/", payload).status_code, 201)

    def test_active_posts_count(self):
        self.make_post(self.ali)
        self.make_post(self.ali, status="pending")
        res = self.client.get("/api/categories/")
        self.assertEqual(res.data[0]["active_posts"], 1)

    def test_cannot_delete_category_with_posts(self):
        self.make_post(self.ali)
        self.login_as(self.admin)
        res = self.client.delete(f"/api/categories/{self.category.id}/")
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_can_delete_empty_category(self):
        empty = Category.objects.create(name="Bo'sh", slug="bosh")
        self.login_as(self.admin)
        self.assertEqual(self.client.delete(f"/api/categories/{empty.id}/").status_code, 204)


class PlaceTests(FindItTestCase):
    payload = {
        "name": "Markaziy kutubxona",
        "place_type": "library",
        "latitude": 41.3,
        "longitude": 69.2,
    }

    def test_only_admin_can_create_place(self):
        self.login_as(self.ali)
        self.assertEqual(self.api_post("/api/places/", self.payload).status_code, 403)
        self.login_as(self.admin)
        res = self.api_post("/api/places/", self.payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["place_type_display"], "Kutubxona")

    def test_place_coordinates_must_be_paired(self):
        self.login_as(self.admin)
        res = self.api_post("/api/places/", {"name": "Bog'", "latitude": 41.3})
        self.assertEqual(res.status_code, 400)

    def test_place_filter_by_type(self):
        Place.objects.create(name="A", place_type="mall")
        Place.objects.create(name="B", place_type="library")
        res = self.client.get("/api/places/", {"place_type": "mall"})
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], "A")
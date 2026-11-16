from core.helpers import FindItTestCase
from notifications.models import Notification
from notifications.services import notify

URL = "/api/notifications/"


class NotificationApiTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.n1 = notify(self.ali, Notification.Kind.SYSTEM, "Birinchi", "Matn 1")
        self.n2 = notify(self.ali, Notification.Kind.MATCH_FOUND, "Ikkinchi", "Matn 2")
        self.foreign = notify(self.vali, Notification.Kind.SYSTEM, "Boshqaning xabari")

    def test_requires_login(self):
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_user_sees_only_own_notifications_newest_first(self):
        self.login_as(self.ali)
        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual([n["id"] for n in res.data["results"]], [self.n2.id, self.n1.id])

    def test_notify_service_saves_fields(self):
        post = self.make_post(self.ali)
        n = notify(self.ali, Notification.Kind.POST_APPROVED, "Sarlavha", "Matn", post=post)
        self.assertEqual((n.user, n.kind, n.post, n.is_read), (self.ali, "post_approved", post, False))

    def test_filter_by_kind_and_read_state(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.get(URL, {"kind": "match_found"}).data["count"], 1)
        self.api_post(f"{URL}{self.n1.id}/read/")
        self.assertEqual(self.client.get(URL, {"is_read": "false"}).data["count"], 1)

    def test_unread_count(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.get(f"{URL}unread-count/").data["unread"], 2)

    def test_mark_one_as_read(self):
        self.login_as(self.ali)
        res = self.api_post(f"{URL}{self.n1.id}/read/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_read"])
        self.assertEqual(self.client.get(f"{URL}unread-count/").data["unread"], 1)

    def test_mark_all_as_read(self):
        self.login_as(self.ali)
        res = self.api_post(f"{URL}read-all/")
        self.assertEqual(res.data["updated"], 2)
        self.assertEqual(self.client.get(f"{URL}unread-count/").data["unread"], 0)
        # boshqa foydalanuvchining xabarlariga tegmaydi
        self.foreign.refresh_from_db()
        self.assertFalse(self.foreign.is_read)

    def test_cannot_touch_foreign_notification(self):
        self.login_as(self.ali)
        self.assertEqual(self.api_post(f"{URL}{self.foreign.id}/read/").status_code, 404)
        self.assertEqual(self.client.delete(f"{URL}{self.foreign.id}/").status_code, 404)

    def test_delete_own_notification(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.delete(f"{URL}{self.n1.id}/").status_code, 204)
        self.assertEqual(self.client.get(URL).data["count"], 1)
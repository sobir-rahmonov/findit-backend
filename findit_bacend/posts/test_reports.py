from core.helpers import FindItTestCase
from posts.models import Post, Report

URL = "/api/reports/"
QUEUE = "/api/moderation/reports/"


class CreateReportTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.vali, Post.Type.FOUND)
        self.login_as(self.ali)

    def test_report_user(self):
        res = self.api_post(URL, {"target_user": self.vali.id, "reason": "spam", "text": "Reklama"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "open")
        self.assertEqual(Report.objects.get().reporter, self.ali)

    def test_report_post(self):
        res = self.api_post(URL, {"post": self.post.id, "reason": "fake"})
        self.assertEqual(res.status_code, 201)

    def test_requires_login(self):
        self.anonymous()
        self.assertEqual(self.api_post(URL, {"post": self.post.id, "reason": "fake"}).status_code, 401)

    def test_needs_exactly_one_target(self):
        both = {"post": self.post.id, "target_user": self.vali.id, "reason": "spam"}
        self.assertEqual(self.api_post(URL, both).status_code, 400)
        self.assertEqual(self.api_post(URL, {"reason": "spam"}).status_code, 400)

    def test_cannot_report_yourself_or_own_post(self):
        res = self.api_post(URL, {"target_user": self.ali.id, "reason": "spam"})
        self.assertEqual(res.status_code, 400)
        own = self.make_post(self.ali)
        self.assertEqual(self.api_post(URL, {"post": own.id, "reason": "spam"}).status_code, 400)

    def test_cannot_report_pending_post(self):
        pending = self.make_post(self.vali, status=Post.Status.PENDING)
        self.assertEqual(self.api_post(URL, {"post": pending.id, "reason": "spam"}).status_code, 400)

    def test_other_reason_needs_text(self):
        res = self.api_post(URL, {"post": self.post.id, "reason": "other"})
        self.assertEqual(res.status_code, 400)
        res = self.api_post(URL, {"post": self.post.id, "reason": "other", "text": "Shubhali e'lon"})
        self.assertEqual(res.status_code, 201)

    def test_duplicate_open_report_rejected(self):
        payload = {"post": self.post.id, "reason": "fake"}
        self.assertEqual(self.api_post(URL, payload).status_code, 201)
        self.assertEqual(self.api_post(URL, payload).status_code, 400)

    def test_user_sees_only_own_reports(self):
        Report.objects.create(reporter=self.ali, post=self.post, reason="fake")
        Report.objects.create(reporter=self.vali, target_user=self.ali, reason="spam")
        res = self.client.get(URL)
        self.assertEqual(res.data["count"], 1)


class ModerateReportTests(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.vali, Post.Type.FOUND)
        self.report = Report.objects.create(reporter=self.ali, post=self.post, reason="fake")

    def test_queue_requires_moderator(self):
        self.login_as(self.ali)
        self.assertEqual(self.client.get(QUEUE).status_code, 403)
        self.login_as(self.moder)
        res = self.client.get(QUEUE)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["reporter_username"], "ali")

    def test_resolve_requires_note(self):
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{self.report.id}/resolve/", {})
        self.assertEqual(res.status_code, 400)

    def test_resolve_notifies_reporter(self):
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{self.report.id}/resolve/", {"note": "Tekshirildi"})
        self.assertEqual(res.status_code, 200)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.RESOLVED)
        self.assertEqual(self.report.handled_by, self.moder)
        self.assertIn("report_resolved", self.kinds(self.ali))

    def test_resolve_can_reject_the_post(self):
        self.login_as(self.moder)
        res = self.api_post(
            f"{QUEUE}{self.report.id}/resolve/", {"note": "Soxta e'lon", "reject_post": True}
        )
        self.assertEqual(res.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.REJECTED)
        self.assertIn("post_rejected", self.kinds(self.vali))

    def test_cannot_reject_post_for_user_report(self):
        report = Report.objects.create(reporter=self.ali, target_user=self.vali, reason="spam")
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{report.id}/resolve/", {"note": "Ha", "reject_post": True})
        self.assertEqual(res.status_code, 400)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.OPEN)

    def test_dismiss_report(self):
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{self.report.id}/dismiss/", {"note": "Dalil yo'q"})
        self.assertEqual(res.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.DISMISSED)
        self.assertIn("report_resolved", self.kinds(self.ali))

    def test_handled_report_cannot_be_handled_again(self):
        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{self.report.id}/dismiss/", {"note": "Asossiz"})
        res = self.api_post(f"{QUEUE}{self.report.id}/resolve/", {"note": "Qayta"})
        self.assertEqual(res.status_code, 400)
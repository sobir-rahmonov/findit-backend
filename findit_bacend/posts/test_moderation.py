from claims.models import Claim
from core.helpers import FindItTestCase
from posts.models import Match, Post

QUEUE = "/api/moderation/posts/"


class ModerationAccessTests(FindItTestCase):
    def test_queue_requires_moderator(self):
        self.assertEqual(self.client.get(QUEUE).status_code, 401)
        self.login_as(self.ali)
        self.assertEqual(self.client.get(QUEUE).status_code, 403)
        self.login_as(self.moder)
        self.assertEqual(self.client.get(QUEUE).status_code, 200)
        self.login_as(self.admin)
        self.assertEqual(self.client.get(QUEUE).status_code, 200)

    def test_user_cannot_approve_or_reject(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.vali)
        self.assertEqual(self.api_post(f"{QUEUE}{post.id}/approve/").status_code, 403)
        res = self.api_post(f"{QUEUE}{post.id}/reject/", {"reason": "Sabab"})
        self.assertEqual(res.status_code, 403)

    def test_default_queue_shows_only_pending_oldest_first(self):
        first = self.make_post(self.ali, status=Post.Status.PENDING, title="Birinchi")
        second = self.make_post(self.vali, status=Post.Status.PENDING, title="Ikkinchi")
        self.make_post(self.ali, status=Post.Status.ACTIVE)
        self.login_as(self.moder)
        res = self.client.get(QUEUE)
        self.assertEqual([p["id"] for p in res.data["results"]], [first.id, second.id])

    def test_moderator_can_filter_by_status(self):
        self.make_post(self.ali, status=Post.Status.PENDING)
        self.make_post(self.ali, status=Post.Status.ACTIVE)
        self.login_as(self.moder)
        res = self.client.get(QUEUE, {"status": "active"})
        self.assertEqual(res.data["count"], 1)


class ApprovePostTests(FindItTestCase):
    def test_approve_activates_post_and_notifies_author(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{post.id}/approve/")
        self.assertEqual(res.status_code, 200)

        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.ACTIVE)
        self.assertEqual(post.moderated_by, self.moder)
        self.assertIsNotNone(post.moderated_at)
        self.assertIn("post_approved", self.kinds(self.ali))

    def test_admin_can_approve_too(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.admin)
        self.assertEqual(self.api_post(f"{QUEUE}{post.id}/approve/").status_code, 200)

    def test_only_pending_post_can_be_approved(self):
        post = self.make_post(self.ali, status=Post.Status.ACTIVE)
        self.login_as(self.moder)
        self.assertEqual(self.api_post(f"{QUEUE}{post.id}/approve/").status_code, 400)

    def test_approving_runs_matching(self):
        self.make_post(self.ali, Post.Type.LOST, title="Qora AirPods quloqchin")
        found = self.make_post(
            self.vali, Post.Type.FOUND, status=Post.Status.PENDING,
            title="Qora AirPods topildi quloqchin",
        )
        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{found.id}/approve/")
        self.assertEqual(Match.objects.count(), 1)
        self.assertIn("match_found", self.kinds(self.ali))


class RejectPostTests(FindItTestCase):
    def test_reject_requires_reason(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.moder)
        self.assertEqual(self.api_post(f"{QUEUE}{post.id}/reject/", {}).status_code, 400)
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PENDING)

    def test_reject_saves_reason_and_notifies_author(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{post.id}/reject/", {"reason": "Rasm noto'g'ri"})
        self.assertEqual(res.status_code, 200)

        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.REJECTED)
        self.assertEqual(post.reject_reason, "Rasm noto'g'ri")
        self.assertIn("post_rejected", self.kinds(self.ali))

    def test_rejected_post_is_not_public(self):
        post = self.make_post(self.ali, status=Post.Status.PENDING)
        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{post.id}/reject/", {"reason": "Spam"})
        self.anonymous()
        self.assertEqual(self.client.get(f"/api/posts/{post.id}/").status_code, 404)

    def test_author_sees_reject_reason(self):
        post = self.make_post(
            self.ali, status=Post.Status.REJECTED, reject_reason="Qoidaga zid"
        )
        self.login_as(self.ali)
        res = self.client.get(f"/api/posts/{post.id}/")
        self.assertEqual(res.data["reject_reason"], "Qoidaga zid")

    def test_reject_removes_matches_and_cancels_pending_claims(self):
        lost = self.make_post(self.ali, Post.Type.LOST)
        found = self.make_post(self.vali, Post.Type.FOUND)
        Match.objects.create(lost_post=lost, found_post=found, score=80)
        claim = Claim.objects.create(
            found_post=found, claimant=self.ali, description="Chizilgan joyi bor"
        )

        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{found.id}/reject/", {"reason": "Soxta e'lon"})

        self.assertEqual(Match.objects.count(), 0)
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.Status.CANCELLED)
        self.assertIn("claim_rejected", self.kinds(self.ali))

    def test_closed_post_cannot_be_rejected(self):
        post = self.make_post(self.ali, status=Post.Status.CLOSED)
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{post.id}/reject/", {"reason": "Kech"})
        self.assertEqual(res.status_code, 400)
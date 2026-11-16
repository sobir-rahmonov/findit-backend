from claims.models import Claim
from core.helpers import FindItTestCase
from posts.models import Post

CLAIMS = "/api/claims/"
QUEUE = "/api/moderation/claims/"
PROOF = "Quloqchin g'ilofining chetida chizilgan joyi bor"


class ClaimBase(FindItTestCase):
    def setUp(self):
        super().setUp()
        self.found = self.make_post(
            self.vali, Post.Type.FOUND, title="Qora AirPods topildi",
            storage_note="Kutubxona ma'muriyatida",
            private_detail="G'ilofida chizilgan joy bor",
        )
        self.lost = self.make_post(self.ali, Post.Type.LOST)

    def payload(self, **extra):
        data = {"found_post": self.found.id, "lost_post": self.lost.id, "description": PROOF}
        data.update(extra)
        return data

    def make_claim(self, claimant=None, **extra):
        return Claim.objects.create(
            found_post=self.found, claimant=claimant or self.ali, description=PROOF, **extra
        )

    def refresh(self, *objs):
        for obj in objs:
            obj.refresh_from_db()


class CreateClaimTests(ClaimBase):
    def test_claim_requires_login(self):
        self.assertEqual(self.api_post(CLAIMS, self.payload()).status_code, 401)

    def test_create_claim_notifies_finder(self):
        self.login_as(self.ali)
        res = self.api_post(CLAIMS, self.payload())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")
        self.assertIn("claim_received", self.kinds(self.vali))

    def test_claim_without_lost_post_is_allowed(self):
        self.login_as(self.ali)
        res = self.api_post(CLAIMS, {"found_post": self.found.id, "description": PROOF})
        self.assertEqual(res.status_code, 201)

    def test_short_description_rejected(self):
        self.login_as(self.ali)
        res = self.api_post(CLAIMS, self.payload(description="Mening"))
        self.assertEqual(res.status_code, 400)

    def test_cannot_claim_own_post(self):
        self.login_as(self.vali)
        res = self.api_post(CLAIMS, {"found_post": self.found.id, "description": PROOF})
        self.assertEqual(res.status_code, 400)

    def test_can_only_claim_active_found_posts(self):
        self.login_as(self.ali)
        self.found.status = Post.Status.HANDOVER
        self.found.save()
        self.assertEqual(self.api_post(CLAIMS, self.payload()).status_code, 400)

        someone_lost = self.make_post(self.vali, Post.Type.LOST)  # FOUND emas
        res = self.api_post(CLAIMS, {"found_post": someone_lost.id, "description": PROOF})
        self.assertEqual(res.status_code, 400)

    def test_lost_post_must_be_own(self):
        foreign = self.make_post(self.vali, Post.Type.LOST)
        self.login_as(self.ali)
        res = self.api_post(CLAIMS, self.payload(lost_post=foreign.id))
        self.assertEqual(res.status_code, 400)

    def test_duplicate_pending_claim_rejected(self):
        self.login_as(self.ali)
        self.assertEqual(self.api_post(CLAIMS, self.payload()).status_code, 201)
        self.assertEqual(self.api_post(CLAIMS, self.payload()).status_code, 400)


class ClaimantViewTests(ClaimBase):
    def test_user_sees_only_own_claims(self):
        self.make_claim(self.ali)
        self.login_as(self.vali)
        self.assertEqual(self.client.get(CLAIMS).data["count"], 0)
        self.login_as(self.ali)
        self.assertEqual(self.client.get(CLAIMS).data["count"], 1)

    def test_other_users_claim_is_not_accessible(self):
        claim = self.make_claim(self.ali)
        self.login_as(self.vali)
        self.assertEqual(self.client.get(f"{CLAIMS}{claim.id}/").status_code, 404)

    def test_pickup_info_hidden_until_approved(self):
        claim = self.make_claim(self.ali)
        self.login_as(self.ali)
        self.assertIsNone(self.client.get(f"{CLAIMS}{claim.id}/").data["pickup_info"])

        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{claim.id}/approve/")
        self.login_as(self.ali)
        res = self.client.get(f"{CLAIMS}{claim.id}/")
        self.assertEqual(res.data["pickup_info"], "Kutubxona ma'muriyatida")

    def test_claimant_can_cancel_pending_claim(self):
        claim = self.make_claim(self.ali)
        self.login_as(self.ali)
        res = self.api_post(f"{CLAIMS}{claim.id}/cancel/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "cancelled")

    def test_cannot_cancel_approved_claim(self):
        claim = self.make_claim(self.ali, status=Claim.Status.APPROVED)
        self.login_as(self.ali)
        self.assertEqual(self.api_post(f"{CLAIMS}{claim.id}/cancel/").status_code, 400)


class ClaimModerationTests(ClaimBase):
    def test_queue_requires_moderator(self):
        self.make_claim()
        self.assertEqual(self.client.get(QUEUE).status_code, 401)
        self.login_as(self.ali)
        self.assertEqual(self.client.get(QUEUE).status_code, 403)

    def test_moderator_sees_private_detail(self):
        self.make_claim()
        self.login_as(self.moder)
        res = self.client.get(QUEUE)
        self.assertEqual(res.data["count"], 1)
        item = res.data["results"][0]
        self.assertEqual(item["claimant_username"], "ali")
        self.assertEqual(item["found_post_detail"]["private_detail"], "G'ilofida chizilgan joy bor")

    def test_default_queue_hides_finished_claims(self):
        self.make_claim()
        self.make_claim(self.moder, status=Claim.Status.REJECTED)
        self.login_as(self.moder)
        self.assertEqual(self.client.get(QUEUE).data["count"], 1)
        self.assertEqual(self.client.get(QUEUE, {"status": "rejected"}).data["count"], 1)

    def test_user_cannot_approve(self):
        claim = self.make_claim()
        self.login_as(self.vali)
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/approve/").status_code, 403)


class ApproveClaimTests(ClaimBase):
    def test_approve_moves_posts_to_handover_and_notifies(self):
        claim = self.make_claim(lost_post=self.lost)
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{claim.id}/approve/", {"note": "Belgilar mos"})
        self.assertEqual(res.status_code, 200)

        self.refresh(claim, self.found, self.lost)
        self.assertEqual(claim.status, Claim.Status.APPROVED)
        self.assertEqual(claim.moderator, self.moder)
        self.assertEqual(self.found.status, Post.Status.HANDOVER)
        self.assertEqual(self.lost.status, Post.Status.HANDOVER)
        self.assertIn("claim_approved", self.kinds(self.ali))
        self.assertIn("claim_approved", self.kinds(self.vali))

    def test_approve_cancels_competing_claims(self):
        winner = self.make_claim(self.ali)
        other_user = self.make_user("third")
        loser = self.make_claim(other_user)

        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{winner.id}/approve/")

        self.refresh(loser)
        self.assertEqual(loser.status, Claim.Status.CANCELLED)
        self.assertIn("claim_rejected", self.kinds(other_user))

    def test_moderator_cannot_approve_own_claim(self):
        claim = self.make_claim(self.moder)
        self.login_as(self.moder)
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/approve/").status_code, 400)

    def test_cannot_approve_twice(self):
        claim = self.make_claim()
        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{claim.id}/approve/")
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/approve/").status_code, 400)


class RejectClaimTests(ClaimBase):
    def test_reject_requires_reason(self):
        claim = self.make_claim()
        self.login_as(self.moder)
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/reject/", {}).status_code, 400)

    def test_reject_notifies_claimant_and_keeps_post_active(self):
        claim = self.make_claim()
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{claim.id}/reject/", {"reason": "Belgilar mos kelmadi"})
        self.assertEqual(res.status_code, 200)

        self.refresh(claim, self.found)
        self.assertEqual(claim.status, Claim.Status.REJECTED)
        self.assertEqual(claim.moderator_note, "Belgilar mos kelmadi")
        self.assertEqual(self.found.status, Post.Status.ACTIVE)
        self.assertIn("claim_rejected", self.kinds(self.ali))

    def test_only_pending_claim_can_be_rejected(self):
        claim = self.make_claim(status=Claim.Status.APPROVED)
        self.login_as(self.moder)
        res = self.api_post(f"{QUEUE}{claim.id}/reject/", {"reason": "Kech"})
        self.assertEqual(res.status_code, 400)


class HandoverTests(ClaimBase):
    def approved_claim(self):
        claim = self.make_claim(lost_post=self.lost)
        self.login_as(self.moder)
        self.api_post(f"{QUEUE}{claim.id}/approve/")
        return claim

    def test_complete_closes_both_posts(self):
        claim = self.approved_claim()
        res = self.api_post(f"{QUEUE}{claim.id}/complete/", {"note": "Pasport bilan topshirildi"})
        self.assertEqual(res.status_code, 200)

        self.refresh(claim, self.found, self.lost)
        self.assertEqual(claim.status, Claim.Status.COMPLETED)
        self.assertEqual(claim.handover_note, "Pasport bilan topshirildi")
        self.assertIsNotNone(claim.handed_over_at)
        for post in (self.found, self.lost):
            self.assertEqual(post.status, Post.Status.CLOSED)
            self.assertIsNotNone(post.closed_at)
        self.assertIn("handover_completed", self.kinds(self.ali))
        self.assertIn("handover_completed", self.kinds(self.vali))

    def test_cannot_complete_pending_claim(self):
        claim = self.make_claim()
        self.login_as(self.moder)
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/complete/").status_code, 400)

    def test_cannot_complete_twice(self):
        claim = self.approved_claim()
        self.api_post(f"{QUEUE}{claim.id}/complete/")
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/complete/").status_code, 400)

    def test_revoke_returns_posts_to_active(self):
        claim = self.approved_claim()
        res = self.api_post(f"{QUEUE}{claim.id}/revoke/", {"reason": "Egasi kelmadi"})
        self.assertEqual(res.status_code, 200)

        self.refresh(claim, self.found, self.lost)
        self.assertEqual(claim.status, Claim.Status.CANCELLED)
        self.assertEqual(self.found.status, Post.Status.ACTIVE)
        self.assertEqual(self.lost.status, Post.Status.ACTIVE)

    def test_revoke_requires_reason(self):
        claim = self.approved_claim()
        self.assertEqual(self.api_post(f"{QUEUE}{claim.id}/revoke/", {}).status_code, 400)
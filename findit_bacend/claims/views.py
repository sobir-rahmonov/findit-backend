from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsModerator
from notifications.models import Notification
from notifications.services import notify

from .models import Claim
from .serializers import (
    ClaimSerializer,
    ModerationClaimSerializer,
    NoteSerializer,
    ReasonSerializer,
)
from .services import (
    approve_claim,
    cancel_claim,
    complete_claim,
    reject_claim,
    revoke_claim,
)


class ClaimViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Da'vogarning o'z da'volari."""

    serializer_class = ClaimSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        return Claim.objects.filter(claimant=self.request.user).select_related(
            "found_post", "lost_post", "moderator"
        )

    def perform_create(self, serializer):
        claim = serializer.save(claimant=self.request.user)
        found = claim.found_post
        notify(
            found.author,
            Notification.Kind.CLAIM_RECEIVED,
            "Buyumingizga da'vo keldi",
            f"«{found.title}» e'loningizga egalik da'vosi yuborildi. Moderator tekshiradi.",
            post=found,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        claim = cancel_claim(self.get_object())
        return Response(self.get_serializer(claim).data)


class ModerationClaimViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ModerationClaimSerializer
    permission_classes = [IsModerator]
    filterset_fields = ["status"]
    ordering_fields = ["created_at"]
    ordering = ["created_at"]  # navbat: eskisi birinchi

    def get_queryset(self):
        qs = Claim.objects.select_related(
            "claimant", "moderator",
            "found_post__category", "found_post__place", "found_post__author",
            "lost_post__category", "lost_post__place", "lost_post__author",
        )
        # Holat berilmasa, kutilayotganlar ko'rsatiladi
        if self.action == "list" and "status" not in self.request.query_params:
            qs = qs.filter(status=Claim.Status.PENDING)
        return qs

    def _respond(self, claim):
        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = approve_claim(self.get_object(), request.user, data.validated_data["note"])
        return self._respond(claim)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = reject_claim(self.get_object(), request.user, data.validated_data["reason"])
        return self._respond(claim)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = complete_claim(self.get_object(), request.user, data.validated_data["note"])
        return self._respond(claim)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        claim = revoke_claim(self.get_object(), request.user, data.validated_data["reason"])
        return self._respond(claim)
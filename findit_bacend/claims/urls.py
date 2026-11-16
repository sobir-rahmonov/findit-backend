from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ClaimViewSet, ModerationClaimViewSet

router = SimpleRouter()
router.register("claims", ClaimViewSet, basename="claim")
router.register("moderation/claims", ModerationClaimViewSet, basename="moderation-claim")

urlpatterns = [
    path("", include(router.urls)),
]
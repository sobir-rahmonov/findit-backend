from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .report_views import ModerationReportViewSet, ReportViewSet
from .views import (
    CategoryViewSet,
    ModerationPostViewSet,
    PlaceViewSet,
    PostViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("places", PlaceViewSet, basename="place")
router.register("posts", PostViewSet, basename="post")
router.register("moderation/posts", ModerationPostViewSet, basename="moderation-post")
router.register("reports", ReportViewSet, basename="report")
router.register("moderation/reports", ModerationReportViewSet, basename="moderation-report")

urlpatterns = [
    path("", include(router.urls)),
]
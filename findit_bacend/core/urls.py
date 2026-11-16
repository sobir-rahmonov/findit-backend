from django.urls import include, path
from rest_framework.routers import SimpleRouter

from accounts.admin_views import AdminUserViewSet

from .views import statistics, system_settings

router = SimpleRouter()
router.register("admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("admin/settings/", system_settings),
    path("admin/statistics/", statistics),
    path("", include(router.urls)),
]
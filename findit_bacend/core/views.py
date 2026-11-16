from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdministrator
from claims.models import Claim
from posts.models import Match, Post, Report

from .models import SystemSettings
from .serializers import SystemSettingsSerializer


@api_view(["GET", "PATCH"])
@permission_classes([IsAdministrator])
def system_settings(request):
    obj = SystemSettings.load()
    if request.method == "PATCH":
        serializer = SystemSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(SystemSettingsSerializer(obj).data)


def _counts(qs, field, choices):
    """Har bir variant bo'yicha soni (0 bo'lsa ham ko'rsatiladi)."""
    data = dict(qs.values_list(field).annotate(c=Count("id")).order_by())
    return {key: data.get(key, 0) for key, _ in choices}


@api_view(["GET"])
@permission_classes([IsAdministrator])
def statistics(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    posts = Post.objects.all()
    claims = Claim.objects.all()
    reports = Report.objects.all()
    users = User.objects.all()

    found_total = posts.filter(
        type=Post.Type.FOUND,
        status__in=[Post.Status.ACTIVE, Post.Status.HANDOVER, Post.Status.CLOSED],
    ).count()
    returned = claims.filter(status=Claim.Status.COMPLETED).count()

    # Oxirgi 14 kun: kuniga nechta yo'qolgan/topilgan e'lon
    days = 14
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    rows = (
        posts.filter(created_at__date__gte=start_day)
        .annotate(day=TruncDate("created_at"))
        .values("day", "type")
        .annotate(c=Count("id"))
        .order_by()
    )
    grid = {}
    for r in rows:
        grid.setdefault(r["day"], {})[r["type"]] = r["c"]
    trend = []
    for i in range(days):
        d = start_day + timedelta(days=i)
        trend.append({
            "date": d.isoformat(),
            "lost": grid.get(d, {}).get(Post.Type.LOST, 0),
            "found": grid.get(d, {}).get(Post.Type.FOUND, 0),
        })

    top_categories = [
        {"name": r["category__name"], "count": r["c"]}
        for r in posts.values("category__name").annotate(c=Count("id")).order_by("-c")[:10]
    ]

    return Response({
        "users": {
            "total": users.count(),
            "by_role": _counts(users, "role", User.Role.choices),
            "blocked": users.filter(is_blocked=True).count(),
            "new_last_7_days": users.filter(date_joined__gte=week_ago).count(),
        },
        "posts": {
            "total": posts.count(),
            "by_status": _counts(posts, "status", Post.Status.choices),
            "by_type": _counts(posts, "type", Post.Type.choices),
            "active_by_type": _counts(
                posts.filter(status=Post.Status.ACTIVE), "type", Post.Type.choices
            ),
            "per_day": trend,
            "top_categories": top_categories,
        },
        "claims": {
            "total": claims.count(),
            "by_status": _counts(claims, "status", Claim.Status.choices),
        },
        "reports": {
            "total": reports.count(),
            "by_status": _counts(reports, "status", Report.Status.choices),
        },
        "matches": {"total": Match.objects.count()},
        "returns": {
            "returned_items": returned,
            "found_items_total": found_total,
            "return_rate_percent": round(returned / found_total * 100, 1) if found_total else 0,
        },
        "queues": {
            "pending_posts": posts.filter(status=Post.Status.PENDING).count(),
            "pending_claims": claims.filter(status=Claim.Status.PENDING).count(),
            "open_reports": reports.filter(status=Report.Status.OPEN).count(),
        },
    })
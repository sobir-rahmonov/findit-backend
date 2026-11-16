from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsModerator

from .models import Report
from .report_serializers import (
    ModerationReportSerializer,
    ReportActionSerializer,
    ReportSerializer,
)
from .report_services import dismiss_report, resolve_report


class ReportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Foydalanuvchining o'z shikoyatlari."""

    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        return Report.objects.filter(reporter=self.request.user).select_related(
            "post", "target_user"
        )

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class ModerationReportViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ModerationReportSerializer
    permission_classes = [IsModerator]
    filterset_fields = ["status", "reason"]
    ordering_fields = ["created_at"]
    ordering = ["created_at"]

    def get_queryset(self):
        qs = Report.objects.select_related(
            "reporter", "handled_by", "target_user", "post", "post__author"
        )
        if self.action == "list" and "status" not in self.request.query_params:
            qs = qs.filter(status=Report.Status.OPEN)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        data = ReportActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        report = resolve_report(
            self.get_object(),
            request.user,
            data.validated_data["note"],
            data.validated_data["reject_post"],
        )
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        data = ReportActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        report = dismiss_report(self.get_object(), request.user, data.validated_data["note"])
        return Response(self.get_serializer(report).data)
from django.db.models import Count, ProtectedError, Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdministratorOrReadOnly, IsModerator
from core.models import SystemSettings

from .filters import PostFilter
from .matching import run_matching
from .models import Category, Match, Place, Post
from .permissions import IsAuthorOrAdmin
from .serializers import (
    CategorySerializer,
    ModerationPostSerializer,
    PlaceSerializer,
    PostSerializer,
    RejectSerializer,
)
from .services import approve_post, reject_post

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdministratorOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        qs = Category.objects.annotate(
            active_posts=Count("posts", filter=Q(posts__status=Post.Status.ACTIVE))
        )
        user = self.request.user
        if user.is_authenticated and user.is_administrator:
            return qs
        return qs.filter(is_active=True)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Bu kategoriyada e'lonlar bor. Uni o'chirmasdan nofaol qiling."},
                status=400,
            )


class PlaceViewSet(viewsets.ModelViewSet):
    serializer_class = PlaceSerializer
    permission_classes = [IsAdministratorOrReadOnly]
    pagination_class = None
    filterset_fields = ["place_type"]
    search_fields = ["name", "address"]

    def get_queryset(self):
        qs = Place.objects.all()
        user = self.request.user
        if user.is_authenticated and user.is_administrator:
            return qs
        return qs.filter(is_active=True)


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    filterset_class = PostFilter
    search_fields = ["title", "description", "brand", "location_detail"]
    ordering_fields = ["created_at", "event_date"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsAuthorOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Post.objects.select_related("category", "place", "author")
        if self.action == "list":
            return qs.filter(status=Post.Status.ACTIVE)  # umumiy ro'yxat: faqat faollar

        user = self.request.user
        if user.is_authenticated and user.is_moderator:
            return qs
        cond = Q(status=Post.Status.ACTIVE)
        if user.is_authenticated:
            cond |= Q(author=user)  # muallif o'z e'lonini har holatda ko'radi
        return qs.filter(cond)

    def perform_create(self, serializer):
        user = self.request.user
        config = SystemSettings.load()

        open_count = Post.objects.filter(
            author=user,
            status__in=[Post.Status.PENDING, Post.Status.ACTIVE, Post.Status.HANDOVER],
        ).count()
        if open_count >= config.max_active_posts_per_user:
            raise serializers.ValidationError(
                {"detail": f"Bir vaqtda {config.max_active_posts_per_user} tadan ko'p faol e'lon bo'lishi mumkin emas."}
            )

        status = Post.Status.PENDING if config.require_moderation else Post.Status.ACTIVE
        post = serializer.save(author=user, status=status)
        if post.status == Post.Status.ACTIVE:
            run_matching(post)

    def perform_update(self, serializer):
        post = serializer.instance
        if post.status in (Post.Status.HANDOVER, Post.Status.CLOSED):
            raise PermissionDenied("Bu e'lonni endi o'zgartirib bo'lmaydi.")

        # Tahrirdan keyin e'lon qayta tekshiruvga ketadi
        config = SystemSettings.load()
        status = Post.Status.PENDING if config.require_moderation else Post.Status.ACTIVE
        post = serializer.save(
            status=status, reject_reason="", moderated_by=None, moderated_at=None
        )
        if post.status == Post.Status.ACTIVE:
            run_matching(post)

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.status in (Post.Status.HANDOVER, Post.Status.CLOSED) and not user.is_administrator:
            raise PermissionDenied("Topshirish jarayonidagi yoki yopilgan e'lonni o'chirib bo'lmaydi.")
        instance.delete()

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """Mening e'lonlarim (hamma holatda)."""
        qs = Post.objects.filter(author=request.user).select_related("category", "place", "author")
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def matches(self, request, pk=None):
        """E'longa mos kelgan e'lonlar (faqat muallif va moderator)."""
        post = self.get_object()
        user = request.user
        if not (user.is_moderator or post.author_id == user.id):
            raise PermissionDenied("Mosliklarni faqat e'lon muallifi ko'ra oladi.")

        qs = Match.objects.filter(Q(lost_post=post) | Q(found_post=post)).select_related(
            "lost_post__category", "lost_post__place", "lost_post__author",
            "found_post__category", "found_post__place", "found_post__author",
        )
        items = []
        for m in qs:
            other = m.found_post if post.type == Post.Type.LOST else m.lost_post
            if other.status != Post.Status.ACTIVE and not user.is_moderator:
                continue
            items.append({
                "id": m.id,
                "score": m.score,
                "reasons": m.reasons,
                "post": PostSerializer(other, context=self.get_serializer_context()).data,
            })
        return Response({"count": len(items), "results": items})




class ModerationPostViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ModerationPostSerializer
    permission_classes = [IsModerator]
    filterset_class = PostFilter
    search_fields = ["title", "description", "brand", "location_detail", "author__username"]
    ordering_fields = ["created_at", "event_date"]
    ordering = ["created_at"]  # navbat: eskisi birinchi

    def get_queryset(self):
        qs = Post.objects.select_related("category", "place", "author", "moderated_by")
        # Holat berilmasa, tekshiruv navbati ko'rsatiladi
        if self.action == "list" and "status" not in self.request.query_params:
            qs = qs.filter(status=Post.Status.PENDING)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        post = approve_post(self.get_object(), request.user)
        return Response(self.get_serializer(post).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = reject_post(self.get_object(), request.user, serializer.validated_data["reason"])
        return Response(self.get_serializer(post).data)
    
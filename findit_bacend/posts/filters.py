import math

import django_filters

from .models import Post


class PostFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    date_from = django_filters.DateFilter(field_name="event_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="event_date", lookup_expr="lte")

    # Xarita bo'yicha: ?lat=41.29&lng=69.24&radius_km=5
    lat = django_filters.NumberFilter(method="noop")
    lng = django_filters.NumberFilter(method="noop")
    radius_km = django_filters.NumberFilter(method="noop")

    class Meta:
        model = Post
        fields = ["type", "place", "color", "status"]

    def noop(self, queryset, name, value):
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        data = self.form.cleaned_data
        lat, lng = data.get("lat"), data.get("lng")
        if lat is not None and lng is not None:
            lat, lng = float(lat), float(lng)
            radius = float(data.get("radius_km") or 5)
            d_lat = radius / 111.0
            d_lng = radius / (111.0 * max(math.cos(math.radians(lat)), 0.01))
            queryset = queryset.filter(
                latitude__gte=lat - d_lat,
                latitude__lte=lat + d_lat,
                longitude__gte=lng - d_lng,
                longitude__lte=lng + d_lng,
            )
        return queryset
import math
import re

from django.db.models import Q

from core.models import SystemSettings
from notifications.models import Notification
from notifications.services import notify

from .models import Match, Post

WEIGHTS = {"color": 20, "brand": 15, "location": 20, "date": 15, "text": 30}


def haversine_km(lat1, lon1, lat2, lon2):
    """Ikki nuqta orasidagi masofa (km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tokens(text):
    text = re.sub(r"[ʻʼ’‘'`]", "", (text or "").lower())
    return {w for w in re.findall(r"\w+", text) if len(w) >= 3}


def color_points(a, b):
    other = Post.Color.OTHER
    if a == b:
        return WEIGHTS["color"] if a != other else WEIGHTS["color"] // 2
    if other in (a, b):
        return 8
    return 0


def brand_points(a, b):
    a = re.sub(r"\W+", "", (a or "").lower())
    b = re.sub(r"\W+", "", (b or "").lower())
    if a and b and (a == b or a in b or b in a):
        return WEIGHTS["brand"]
    return 0


def location_points(lost, found, config):
    """(ball, masofa) yoki juda uzoq bo'lsa None."""
    distance = None
    if lost.has_coordinates and found.has_coordinates:
        distance = haversine_km(lost.latitude, lost.longitude, found.latitude, found.longitude)
        if distance > config.match_max_distance_km:
            return None

    if lost.place_id and lost.place_id == found.place_id:
        return WEIGHTS["location"], distance
    if distance is None:
        return 0, None
    if distance <= 0.3:
        return 20, distance
    if distance <= 1:
        return 15, distance
    if distance <= 3:
        return 10, distance
    return 5, distance


def date_points(lost, found, config):
    """Sana bo'yicha ball yoki mantiqsiz bo'lsa None."""
    diff = (found.event_date - lost.event_date).days
    if diff < -1 or diff > config.match_date_window_days:
        return None
    if diff <= 0:
        return 15
    if diff <= 1:
        return 12
    if diff <= 3:
        return 9
    if diff <= 7:
        return 6
    return 3


def text_points(lost, found):
    a = tokens(f"{lost.title} {lost.description}")
    b = tokens(f"{found.title} {found.description}")
    if not a or not b:
        return 0
    overlap = len(a & b) / min(len(a), len(b))
    return round(WEIGHTS["text"] * overlap)


def compute_score(lost, found, config):
    """(ball, tafsilot) yoki juft mos kelmasa None."""
    loc = location_points(lost, found, config)
    if loc is None:
        return None
    date_pts = date_points(lost, found, config)
    if date_pts is None:
        return None

    location_pts, distance = loc
    reasons = {
        "color": color_points(lost.color, found.color),
        "brand": brand_points(lost.brand, found.brand),
        "location": location_pts,
        "date": date_pts,
        "text": text_points(lost, found),
        "distance_km": round(distance, 2) if distance is not None else None,
    }
    total = sum(v for k, v in reasons.items() if k != "distance_km")
    return min(100, total), reasons


def run_matching(post):
    """
    Faol e'lonni qarama-qarshi turdagi faol e'lonlar bilan solishtiradi.
    Yangi mosliklar uchun ikkala egasiga bildirishnoma yuboradi.
    """
    config = SystemSettings.load()
    opposite = Post.Type.FOUND if post.type == Post.Type.LOST else Post.Type.LOST

    candidates = (
        Post.objects.filter(
            type=opposite,
            status=Post.Status.ACTIVE,
            category_id=post.category_id,
        )
        .exclude(author_id=post.author_id)
        .select_related("author", "place")
    )

    kept_ids = []
    created = []

    for other in candidates:
        lost, found = (post, other) if post.type == Post.Type.LOST else (other, post)
        result = compute_score(lost, found, config)
        if result is None:
            continue
        score, reasons = result
        if score < config.match_threshold:
            continue

        match, was_created = Match.objects.update_or_create(
            lost_post=lost,
            found_post=found,
            defaults={"score": score, "reasons": reasons},
        )
        kept_ids.append(match.pk)
        if was_created:
            created.append(match)
            notify(
                lost.author,
                Notification.Kind.MATCH_FOUND,
                "Mos buyum topildi",
                f"«{lost.title}» e'loningizga {score}% mos topilgan e'lon bor: «{found.title}».",
                post=found,
            )
            notify(
                found.author,
                Notification.Kind.MATCH_FOUND,
                "Egasi bo'lishi mumkin",
                f"«{found.title}» e'loningizga {score}% mos yo'qolgan e'lon bor: «{lost.title}».",
                post=lost,
            )

    # E'lon qayta faollashtirilganda eskirgan mosliklar tozalanadi
    Match.objects.filter(Q(lost_post=post) | Q(found_post=post)).exclude(
        pk__in=kept_ids
    ).delete()

    return created
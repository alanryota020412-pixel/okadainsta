from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .forms import CircleForm, ProfileForm
from .models import (
    Circle,
    Conversation,
    Favorite,
    Message,
    MessageRead,
    Notification,
    Post,
    PostView,
    Profile,
    Tag,
    PostImage,
)


# =========================
# App（単一画面）
# =========================
def app(request):
    tab = request.GET.get("tab") or "home"
    allowed_tabs = {"home", "search", "create", "messages", "profile", "profile_edit"}
    if tab not in allowed_tabs:
        tab = "home"

    posts_qs = (
        Post.objects.all()
        .select_related("author")
        .prefetch_related("tags", "images")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
            image_count=Count("images", distinct=True),
        )
    )

    sort = request.GET.get("sort") or "recent"
    if sort == "popular":
        posts_qs = posts_qs.order_by("-views_count", "-created_at")
    elif sort == "fav":
        posts_qs = posts_qs.order_by("-favs_count", "-created_at")
    else:
        posts_qs = posts_qs.order_by("-event_at", "-created_at")

    posts = list(posts_qs[:50])

    # ---------------- SEARCH ----------------
    search_query = (request.GET.get("q", "") or "").strip()
    category = request.GET.get("category", "")
    tag = request.GET.get("tag", "")
    only_open = request.GET.get("open") == "1"

    search_results = (
        Post.objects.all()
        .prefetch_related("tags")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
        )
    )

    if search_query:
        search_results = (
            search_results.filter(title__icontains=search_query)
            | search_results.filter(circle_name__icontains=search_query)
            | search_results.filter(place__icontains=search_query)
        )

    if category:
        search_results = search_results.filter(category=category)

    if tag:
        search_results = search_results.filter(tags__name=tag)

    if only_open:
        now = timezone.now()
        search_results = search_results.filter(event_at__gte=now).exclude(status="closed")

    search_results = search_results.order_by("-event_at", "-created_at")[:50]

    circle_results = Circle.objects.none()
    if search_query:
        circle_results = (
            Circle.objects.filter(name__icontains=search_query)
            .exclude(name="")
            .order_by("name")[:50]
        )

    selected_circle = None
    circle_id = request.GET.get("circle_id")
    if circle_id:
        selected_circle = Circle.objects.filter(id=circle_id).first()

    tags = Tag.objects.all().order_by("name")
    category_choices = Post.CATEGORY_CHOICES

    profile = None
    circle = None
    my_posts = []
    saved_posts = []
    unread_notifs = 0
    conversations = []
    profile_form = None

    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        circle, _ = Circle.objects.get_or_create(owner=request.user)

        my_posts = Post.objects.filter(author=request.user).order_by("-created_at")[:50]
        saved_posts = Post.objects.filter(favorites=request.user).order_by("-created_at")[:50]
        unread_notifs = Notification.objects.filter(user=request.user, is_read=False).count()

        if tab == "profile_edit":
            if request.method == "POST":
                profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
                if profile_form.is_valid():
                    profile_form.save()
                    return redirect("/?tab=profile")
            else:
                profile_form = ProfileForm(instance=profile)

    if tab == "profile_edit" and not request.user.is_authenticated:
        return redirect("account_login")

    ctx = {
        "initial_tab": tab,
        "posts": posts,
        "search_query": search_query,
        "search_results": search_results,
        "circle_results": circle_results,
        "selected_circle": selected_circle,
        "tags": tags,
        "category_choices": category_choices,
        "profile": profile,
        "circle": circle,
        "my_posts": my_posts,
        "saved_posts": saved_posts,
        "unread_notifs": unread_notifs,
        "conversations": conversations,
        "profile_form": profile_form,
    }
    return render(request, "core/app.html", ctx)


# =========================
# Post Detail JSON
# =========================
def post_detail_json(request, pk):
    p = get_object_or_404(
        Post.objects.prefetch_related("tags", "images").select_related("author"),
        pk=pk,
    )

    seen = request.session.get("seen_posts", [])
    if pk not in seen:
        PostView.objects.create(
            post=p,
            user=request.user if request.user.is_authenticated else None,
        )
        seen.append(pk)
        request.session["seen_posts"] = seen

    return JsonResponse(
        {
            "id": p.id,
            "title": p.title,
            "circle_name": p.circle_name,
            "place": p.place,
            "detail": p.detail,
            "event_at": p.event_at.strftime("%Y/%m/%d %H:%M") if p.event_at else "",
            "tags": [t.name for t in p.tags.all()],
            "image_urls": [im.image.url for im in p.images.all()],
            "image_url": p.image.url if getattr(p, "image", None) else None,
        }
    )


# =========================
# Post Create（複数画像対応）
# =========================
@login_required
@csrf_exempt
def post_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        event_at_raw = request.POST.get("event_at", "").strip()

        if not title or not event_at_raw:
            return render(
                request,
                "core/app.html",
                {"initial_tab": "create", "errors": ["title/event_at required"]},
            )

        dt = parse_datetime(event_at_raw)
        if dt is None:
            dt = timezone.datetime.fromisoformat(event_at_raw)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        images = request.FILES.getlist("images")
        single = request.FILES.get("image")
        if not images and single:
            images = [single]

        p = Post(
            author=request.user,
            title=title,
            circle_name=request.POST.get("circle_name", "").strip(),
            place=request.POST.get("place", "").strip(),
            detail=request.POST.get("detail", "").strip(),
            event_at=dt,
        )

        if images:
            p.image = images[0]

        p.save()

        for img in images:
            PostImage.objects.create(post=p, image=img)

        return redirect("/?tab=home")

    return render(request, "core/app.html", {"initial_tab": "create"})


# =========================
# Favorite Toggle
# =========================
@login_required
@require_POST
def toggle_favorite(request, pk):
    p = get_object_or_404(Post, pk=pk)
    fav = Favorite.objects.filter(user=request.user, post=p).first()

    if fav:
        fav.delete()
        is_fav = False
    else:
        Favorite.objects.create(user=request.user, post=p)
        is_fav = True

    favs_count = Favorite.objects.filter(post=p).count()
    return JsonResponse({"ok": True, "is_fav": is_fav, "favs_count": favs_count})
from django.shortcuts import render, redirect
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth import get_user_model

from .models import Post, Tag, Profile, Circle
from .forms import ProfileForm, CircleForm, PostCreateForm


def _get_guest_user():
    User = get_user_model()
    # email必須のUserだとここで失敗する場合あり。その時はUser定義に合わせて defaults を直す。
    user, _ = User.objects.get_or_create(username="guest", defaults={"email": ""})
    return user


def home(request):
    initial_tab = request.GET.get("tab", "home")

    guest = _get_guest_user()
    profile, _ = Profile.objects.get_or_create(user=guest)
    circle, _ = Circle.objects.get_or_create(owner=guest)

    # ホームに出す投稿（お気に入り数/閲覧数も付ける）
    posts = (
        Post.objects
        .select_related("author")
        .prefetch_related("tags")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
        )
        .order_by("-event_at")[:30]
    )

    # 検索
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    tag = request.GET.get("tag", "").strip()
    only_open = request.GET.get("open") == "1"

    search_results = (
        Post.objects
        .prefetch_related("tags")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
        )
        .order_by("-event_at")
    )

    if q:
        search_results = search_results.filter(
            Q(title__icontains=q) | Q(circle_name__icontains=q) | Q(place__icontains=q)
        )
    if category:
        search_results = search_results.filter(category=category)
    if tag:
        search_results = search_results.filter(tags__name=tag)
    if only_open:
        search_results = search_results.filter(status="open")

    search_results = search_results.distinct()[:50]

    ctx = {
        "initial_tab": initial_tab,
        "posts": posts,
        "tags": Tag.objects.order_by("name"),
        "category_choices": Post.CATEGORY_CHOICES,

        "search_query": q,
        "category": category,
        "tag": tag,
        "only_open": only_open,
        "search_results": search_results,

        # プロフィール表示/編集
        "profile": profile,
        "circle": circle,
        "profile_form": ProfileForm(instance=profile),
        "circle_form": CircleForm(instance=circle),

        # 投稿作成フォーム
        "post_form": PostCreateForm(),
    }
    return render(request, "core/app.html", ctx)


def profile_save(request):
    if request.method != "POST":
        return redirect("/?tab=profile")

    guest = _get_guest_user()
    profile, _ = Profile.objects.get_or_create(user=guest)
    circle, _ = Circle.objects.get_or_create(owner=guest)

    profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
    circle_form = CircleForm(request.POST, instance=circle)

    if profile_form.is_valid() and circle_form.is_valid():
        profile_form.save()
        circle_form.save()
        messages.success(request, "プロフィールを保存しました。")
        return redirect("/?tab=profile")

    # エラー時はそのままフォーム付きで返す
    posts = (
        Post.objects
        .prefetch_related("tags")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
        )
        .order_by("-event_at")[:30]
    )

    ctx = {
        "initial_tab": "profile",
        "posts": posts,
        "tags": Tag.objects.order_by("name"),
        "category_choices": Post.CATEGORY_CHOICES,
        "search_query": "",
        "category": "",
        "tag": "",
        "only_open": False,
        "search_results": [],
        "profile": profile,
        "circle": circle,
        "profile_form": profile_form,
        "circle_form": circle_form,
        "post_form": PostCreateForm(),
    }
    return render(request, "core/app.html", ctx)


def post_create(request):
    if request.method != "POST":
        return redirect("/?tab=create")

    guest = _get_guest_user()
    circle, _ = Circle.objects.get_or_create(owner=guest)

    form = PostCreateForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "入力にエラーがあります。")
        return redirect("/?tab=create")

    post = form.save(commit=False)
    post.author = guest
    if not post.circle_name:
        post.circle_name = circle.name or "guest-circle"
    post.save()

    # Tag 保存（カンマ区切り）
    raw = (form.cleaned_data.get("tags") or "").strip()
    if raw:
        names = [t.strip() for t in raw.split(",") if t.strip()]
        tag_objs = []
        for name in names:
            obj, _ = Tag.objects.get_or_create(name=name)
            tag_objs.append(obj)
        post.tags.set(tag_objs)

    messages.success(request, "投稿を作成しました。")
    return redirect("/?tab=home")

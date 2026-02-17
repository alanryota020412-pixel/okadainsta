from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .forms import CircleForm, PostCreateForm, ProfileForm
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


# -------------------------
# App（単一画面）
# -------------------------
def app(request):
    tab = request.GET.get("tab") or "home"

    # HOME: posts
    posts_qs = (
        Post.objects.all()
        .select_related("author")
        .prefetch_related("tags", "images")  # ← 追加
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
            image_count=Count("images", distinct=True),  # ← 追加
        )
    )


    # 並び替え
    sort = request.GET.get("sort") or "recent"
    if sort == "popular":
        posts_qs = posts_qs.order_by("-views_count", "-created_at")
    elif sort == "fav":
        posts_qs = posts_qs.order_by("-favs_count", "-created_at")
    else:
        posts_qs = posts_qs.order_by("-event_at", "-created_at")

    posts = list(posts_qs[:50])

    # SEARCH
    search_query = request.GET.get("q", "")
    category = request.GET.get("category", "")
    tag = request.GET.get("tag", "")
    only_open = request.GET.get("open") == "1"

    search_results = Post.objects.all().prefetch_related("tags").annotate(
        favs_count=Count("favorites", distinct=True),
        views_count=Count("views", distinct=True),
    )

    if search_query:
        search_results = search_results.filter(
            title__icontains=search_query
        ) | search_results.filter(circle_name__icontains=search_query) | search_results.filter(place__icontains=search_query)

    if category:
        search_results = search_results.filter(category=category)

    if tag:
        search_results = search_results.filter(tags__name=tag)

    if only_open:
        # 終了は除外（event_at 過去 or closed）
        now = timezone.now()
        search_results = search_results.filter(event_at__gte=now).exclude(status="closed")

    search_results = search_results.order_by("-event_at", "-created_at")[:50]

    # tags / choices
    tags = Tag.objects.all().order_by("name")
    category_choices = Post.CATEGORY_CHOICES

    # profile / circle
    profile = None
    circle = None
    my_posts = []
    saved_posts = []
    unread_notifs = 0
    conversations = []

    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        circle, _ = Circle.objects.get_or_create(owner=request.user)

        my_posts = (
            Post.objects.filter(author=request.user)
            .annotate(favs_count=Count("favorites", distinct=True), views_count=Count("views", distinct=True))
            .order_by("-created_at")[:50]
        )

        saved_posts = (
            Post.objects.filter(favorites=request.user)
            .annotate(favs_count=Count("favorites", distinct=True), views_count=Count("views", distinct=True))
            .order_by("-created_at")[:50]
        )

        unread_notifs = Notification.objects.filter(user=request.user, is_read=False).count()

        # conversations list
        conversations = []
        convo_qs = (
            Conversation.objects.filter(participants=request.user)
            .prefetch_related("participants", "messages")
            .order_by("-updated_at")[:50]
        )
        for c in convo_qs:
            last = c.messages.order_by("-created_at").first()
            last_text = last.body if last else ""
            # unread count
            read = MessageRead.objects.filter(conversation=c, user=request.user).first()
            last_read_at = read.last_read_at if read else timezone.make_aware(timezone.datetime.min)
            unread = c.messages.filter(created_at__gt=last_read_at).exclude(sender=request.user).count()

            conversations.append({
                "id": c.id,
                "title": c.title or f"Conversation {c.id}",
                "last_message": last_text,
                "unread": unread,
            })

    ctx = {
        "initial_tab": tab,
        "posts": posts,
        "sort": sort,

        "search_query": search_query,
        "category": category,
        "tag": tag,
        "only_open": only_open,
        "search_results": search_results,

        "tags": tags,
        "category_choices": category_choices,

        "profile": profile,
        "circle": circle,
        "my_posts": my_posts,
        "saved_posts": saved_posts,
        "unread_notifs": unread_notifs,
        "conversations": conversations,
    }
    return render(request, "core/app.html", ctx)


# -------------------------
# Post: detail JSON + view count
# -------------------------
def post_detail_json(request, pk):
    p = get_object_or_404(
        Post.objects.prefetch_related("tags", "images").select_related("author"),
        pk=pk
    )

    # view count（そのまま）

    data = {
        "id": p.id,
        "title": p.title,
        "circle_name": p.circle_name,
        "place": p.place,
        "detail": p.detail,
        "event_at": p.event_at.strftime("%Y/%m/%d %H:%M") if p.event_at else "",
        "status": p.effective_status,
        "category": p.category,
        "tags": [t.name for t in p.tags.all()],

        # ✅ 追加：複数画像
        "image_urls": [im.image.url for im in p.images.all()],

        # （互換のため残すなら残してOK）
        "image_url": p.image.url if getattr(p, "image", None) else None,

        "is_owner": (request.user.is_authenticated and p.author_id == request.user.id),
        "can_fav": request.user.is_authenticated,
    }
    return JsonResponse(data)

# -------------------------
# Post: create/edit/delete
# -------------------------
@login_required
@csrf_exempt  # login実装後に外す
def post_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        event_at_raw = request.POST.get("event_at", "").strip()

        if not title or not event_at_raw:
            return render(request, "core/app.html", {"initial_tab":"create", "errors":["title/event_at required"]})

        dt = parse_datetime(event_at_raw)
        if dt is None:
            dt = timezone.datetime.fromisoformat(event_at_raw)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        print("DEBUG user", request.user.id, request.user.username,
              "has_circle", hasattr(request.user, "circle"),
              "circle_name", getattr(getattr(request.user, "circle", None), "name", None))

        # ✅ ここで必ず定義（新:複数 / 旧:単数 両対応）
        images = request.FILES.getlist("images")
        single = request.FILES.get("image")
        if not images and single:
            images = [single]

        p = Post(
            author=request.user,
            title=title,
            circle_name=request.POST.get("circle_name","").strip(),
            place=request.POST.get("place","").strip(),
            detail=request.POST.get("detail","").strip(),
            event_at=dt,
        )

        # ✅ ここで参照しても NameError にならない
        if images:
            p.image = images[0]  # 1枚目だけ保存（既存 p.image 参照を壊さない）

        p.save()

        # ✅ 複数をDBに保存
        for img in images:
            PostImage.objects.create(post=p, image=img)

        return redirect("/?tab=home")

    return render(request, "core/app.html", {"initial_tab":"create"})



# -------------------------
# Favorite toggle
# -------------------------
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
        # notif to owner
        if p.author_id != request.user.id:
            Notification.objects.create(
                user=p.author,
                notif_type="favorite",
                text=f"{request.user.username} が保存しました: {p.title}",
                url="/?tab=home",
            )

    favs_count = Favorite.objects.filter(post=p).count()
    return JsonResponse({"ok": True, "is_fav": is_fav, "favs_count": favs_count})


# -------------------------
# Profile / Circle save
# -------------------------
@login_required
@require_POST
def profile_save(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    circle, _ = Circle.objects.get_or_create(owner=request.user)

    p_form = ProfileForm(request.POST, request.FILES, instance=profile)
    c_form = CircleForm(request.POST, instance=circle)

    if p_form.is_valid() and c_form.is_valid():
        p_form.save()
        c_form.save()
        Notification.objects.create(
            user=request.user,
            notif_type="participation",
            text="プロフィールを更新しました",
            url="/?tab=profile",
        )
        return redirect("/?tab=profile")
    # エラー時も app に返す
    return render(request, "core/app.html", {
        "initial_tab": "profile",
        "profile": profile,
        "circle": circle,
        "profile_form": p_form,
        "circle_form": c_form,
    })


# -------------------------
# Messages (簡易DM)
# -------------------------
@login_required
def start_conversation(request, post_id):
    post = get_object_or_404(Post, pk=post_id)

    # 自分と投稿者の2人DM（既存あれば再利用）
    me = request.user
    other = post.author
    if me.id == other.id:
        return redirect("/?tab=messages")

    # 既存探索（簡易：post紐づきで同じ2人の会話）
    existing = Conversation.objects.filter(post=post, is_group=False, participants=me).filter(participants=other).first()
    if existing:
        return redirect(f"/?tab=messages&open_convo={existing.id}")

    convo = Conversation.objects.create(
        title=f"{post.title} の問い合わせ",
        is_group=False,
        post=post,
        updated_at=timezone.now(),
    )
    convo.participants.add(me, other)

    Message.objects.create(conversation=convo, sender=me, body="はじめまして！投稿を見て連絡しました。")
    Notification.objects.create(
        user=other,
        notif_type="message",
        text=f"新しいメッセージ: {post.title}",
        url="/?tab=messages",
    )
    return redirect(f"/?tab=messages&open_convo={convo.id}")


@login_required
def conversation_json(request, convo_id):
    convo = get_object_or_404(Conversation, pk=convo_id, participants=request.user)
    msgs = convo.messages.select_related("sender").order_by("created_at")[:200]

    # mark read
    read, _ = MessageRead.objects.get_or_create(conversation=convo, user=request.user)
    read.last_read_at = timezone.now()
    read.save(update_fields=["last_read_at"])

    return JsonResponse({
        "ok": True,
        "id": convo.id,
        "title": convo.title,
        "messages": [
            {
                "id": m.id,
                "sender": m.sender.username,
                "is_me": m.sender_id == request.user.id,
                "body": m.body,
                "created_at": m.created_at.strftime("%m/%d %H:%M"),
            }
            for m in msgs
        ]
    })


@login_required
@require_POST
def send_message(request, convo_id):
    convo = get_object_or_404(Conversation, pk=convo_id, participants=request.user)
    body = (request.POST.get("body") or "").strip()
    if not body:
        return HttpResponseBadRequest("empty")

    Message.objects.create(conversation=convo, sender=request.user, body=body)
    convo.updated_at = timezone.now()
    convo.save(update_fields=["updated_at"])

    # notif to others
    others = convo.participants.exclude(id=request.user.id)
    for u in others:
        Notification.objects.create(
            user=u,
            notif_type="message",
            text=f"新しいメッセージ: {convo.title}",
            url="/?tab=messages",
        )

    return redirect(f"/?tab=messages&open_convo={convo.id}")


# -------------------------
# Notifications
# -------------------------
@login_required
def notifications_json(request):
    notifs = Notification.objects.filter(user=request.user).order_by("-created_at")[:50]
    return JsonResponse({
        "ok": True,
        "unread": Notification.objects.filter(user=request.user, is_read=False).count(),
        "items": [
            {
                "id": n.id,
                "type": n.notif_type,
                "text": n.text,
                "url": n.url,
                "is_read": n.is_read,
                "created_at": n.created_at.strftime("%m/%d %H:%M"),
            }
            for n in notifs
        ]
    })


@login_required
@require_POST
def notifications_mark_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})

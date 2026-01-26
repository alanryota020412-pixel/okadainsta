# core/views.py
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages

from .models import (
    Profile, Circle, Tag, Post, Favorite, Participation,
    Conversation, Message, MessageRead, Notification, PostView
)


# =========================
# 内部ユーティリティ
# =========================
def _ensure_profile_circle(user):
    Profile.objects.get_or_create(user=user)
    Circle.objects.get_or_create(owner=user, defaults={"name": f"{user.username}のサークル"})


def _conversation_title_fallback(convo: Conversation, me):
    others = convo.participants.exclude(id=me.id)[:3]
    names = [u.username for u in others]
    if convo.is_group:
        return convo.title or (" / ".join(names) if names else "グループ")
    return names[0] if names else "DM"


def _conversation_unread_count(convo: Conversation, user):
    read, _ = MessageRead.objects.get_or_create(conversation=convo, user=user)
    return convo.messages.filter(created_at__gt=read.last_read_at).exclude(sender=user).count()


# =========================
# メイン（新入生も閲覧OK）
# =========================
def app(request):
    user = request.user
    is_auth = user.is_authenticated

    profile = None
    circle = None
    unread_notifs = 0
    conversations_payload = []

    if is_auth:
        _ensure_profile_circle(user)
        profile = user.profile
        circle = getattr(user, "circle", None)
        unread_notifs = Notification.objects.filter(user=user, is_read=False).count()

        conversations = (
            Conversation.objects.filter(participants=user)
            .order_by("-updated_at")
            .distinct()
        )
        payload = []
        for c in conversations[:50]:
            last_msg = c.messages.order_by("-created_at").first()
            unread = _conversation_unread_count(c, user)
            payload.append({
                "id": c.id,
                "title": c.title or _conversation_title_fallback(c, user),
                "updated_at": c.updated_at,
                "last_message": last_msg.body if last_msg else "",
                "unread": unread,
            })
        conversations_payload = payload

    tab = request.GET.get("tab", "home")
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    tag = (request.GET.get("tag") or "").strip()
    only_open = request.GET.get("open") == "1"
    now = timezone.now()

    posts_qs = (
        Post.objects.all()
        .annotate(
            favs_count=Count("favorite", distinct=True),
            views_count=Count("views", distinct=True),
        )
        .select_related("author")
        .prefetch_related("tags")
    )

    # 自動終了扱い（event_atが過去なら「終了」表示用）
    # DBのstatusを自動で書き換えるのは、重いのでまず表示だけここで扱う

    if only_open:
        posts_qs = posts_qs.filter(status="open", event_at__gte=now)

    if category:
        posts_qs = posts_qs.filter(category=category)

    if tag:
        posts_qs = posts_qs.filter(tags__name=tag)

    # 検索（タイトル/サークル名/場所）
    if q:
        search_results = posts_qs.filter(
            Q(title__icontains=q) |
            Q(circle_name__icontains=q) |
            Q(place__icontains=q)
        ).order_by("event_at", "-created_at")
    else:
        search_results = posts_qs.order_by("event_at", "-created_at")

    # ホーム：直近 + 人気
    posts_home = posts_qs.order_by("event_at", "-favs_count", "-views_count", "-created_at")

    my_posts = Post.objects.none()
    saved_posts = Post.objects.none()
    if is_auth:
        my_posts = Post.objects.filter(author=user).order_by("-created_at")
        saved_posts = Post.objects.filter(favorites=user).order_by("-created_at")

    tags = Tag.objects.order_by("name")[:50]

    ctx = {
        "now": now,
        "initial_tab": tab,
        "profile": profile,
        "circle": circle,
        "posts": posts_home[:100],
        "search_query": q,
        "search_results": search_results[:200],
        "my_posts": my_posts[:100],
        "saved_posts": saved_posts[:100],
        "conversations": conversations_payload,
        "unread_notifs": unread_notifs,
        "tags": tags,
        "category": category,
        "tag": tag,
        "only_open": only_open,
        "category_choices": Post.CATEGORY_CHOICES,
    }
    return render(request, "core/app.html", ctx)


# =========================
# プロフィール & サークル編集
# =========================
@login_required
def profile_update(request):
    if request.method != "POST":
        return redirect("/?tab=profile")

    _ensure_profile_circle(request.user)
    profile = request.user.profile

    profile.display_name = request.POST.get("display_name", "").strip()
    profile.school_year = request.POST.get("school_year", "").strip()
    profile.role = request.POST.get("role", "").strip()
    profile.bio = request.POST.get("bio", "").strip()

    if request.FILES.get("avatar"):
        profile.avatar = request.FILES["avatar"]

    profile.save()
    messages.success(request, "プロフィールを保存しました。")
    return redirect("/?tab=profile")


@login_required
def circle_update(request):
    if request.method != "POST":
        return redirect("/?tab=profile")

    _ensure_profile_circle(request.user)
    circle = request.user.circle

    circle.name = request.POST.get("name", "").strip() or circle.name
    circle.activity_days = request.POST.get("activity_days", "").strip()
    circle.members_count = int(request.POST.get("members_count") or 0)
    circle.sns_link = request.POST.get("sns_link", "").strip()
    circle.description = request.POST.get("description", "").strip()

    circle.save()
    messages.success(request, "サークル情報を保存しました。")
    return redirect("/?tab=profile")


# =========================
# 投稿 作成/編集/削除
# =========================
@login_required
def post_create(request):
    if request.method != "POST":
        return redirect("/?tab=create")

    _ensure_profile_circle(request.user)
    circle = request.user.circle

    title = request.POST.get("title", "").strip()
    circle_name = request.POST.get("circle_name", "").strip() or circle.name
    place = request.POST.get("place", "").strip()
    detail = request.POST.get("detail", "").strip()
    event_at = request.POST.get("event_at", "").strip()
    status = request.POST.get("status", "open")
    category = request.POST.get("category", "other")
    tags_str = request.POST.get("tags", "").strip()

    if not title or not event_at:
        messages.error(request, "タイトルと日時は必須です。")
        return redirect("/?tab=create")

    # datetime-local -> aware datetime
    try:
        dt = timezone.datetime.fromisoformat(event_at)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        messages.error(request, "日時の形式が正しくありません。")
        return redirect("/?tab=create")

    post = Post.objects.create(
        author=request.user,
        title=title,
        circle_name=circle_name,
        place=place,
        detail=detail,
        event_at=dt,
        status=status,
        category=category,
        image=request.FILES.get("image"),
    )

    # tags
    if tags_str:
        names = [t.strip() for t in tags_str.split(",") if t.strip()]
        for n in names[:20]:
            tag_obj, _ = Tag.objects.get_or_create(name=n)
            post.tags.add(tag_obj)

    messages.success(request, "投稿しました。")
    return redirect("/?tab=home")


@login_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        return redirect("/?tab=home")

    if request.method != "POST":
        return redirect("/?tab=home")

    post.title = request.POST.get("title", "").strip()
    post.circle_name = request.POST.get("circle_name", "").strip()
    post.place = request.POST.get("place", "").strip()
    post.detail = request.POST.get("detail", "").strip()
    post.status = request.POST.get("status", "open")
    post.category = request.POST.get("category", "other")

    event_at = request.POST.get("event_at", "").strip()
    try:
        dt = timezone.datetime.fromisoformat(event_at)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        post.event_at = dt
    except Exception:
        pass

    post.save()

    # tags update（置き換え）
    tags_str = request.POST.get("tags", "").strip()
    post.tags.clear()
    if tags_str:
        names = [t.strip() for t in tags_str.split(",") if t.strip()]
        for n in names[:20]:
            tag_obj, _ = Tag.objects.get_or_create(name=n)
            post.tags.add(tag_obj)

    messages.success(request, "投稿を更新しました。")
    return redirect("/?tab=home")


@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        return redirect("/?tab=home")
    if request.method == "POST":
        post.delete()
        messages.success(request, "投稿を削除しました。")
    return redirect("/?tab=home")


# =========================
# お気に入り
# =========================
@login_required
def favorite_toggle(request, pk):
    post = get_object_or_404(Post, pk=pk)
    obj, created = Favorite.objects.get_or_create(user=request.user, post=post)
    if not created:
        obj.delete()

    # 通知（投稿者へ）
    if post.author != request.user:
        Notification.objects.create(
            user=post.author,
            notif_type="favorite",
            text=f"あなたの投稿「{post.title}」がお気に入りされました",
            url="/?tab=home",
        )
    return JsonResponse({"ok": True})


# =========================
# 参加申請 → DM作成
# =========================
@login_required
def apply_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    now = timezone.now()
    if post.status != "open" or post.event_at < now:
        return JsonResponse({"ok": False})

    part, created = Participation.objects.get_or_create(post=post, user=request.user)

    # DM作成（申請者と投稿者）
    convo = (
        Conversation.objects.filter(is_group=False, participants=request.user)
        .filter(participants=post.author)
        .distinct()
        .first()
    )
    if not convo:
        convo = Conversation.objects.create(is_group=False, title="")
        convo.participants.add(request.user, post.author)

    convo.updated_at = timezone.now()
    convo.save()

    # 通知（代表へ）
    if post.author != request.user:
        Notification.objects.create(
            user=post.author,
            notif_type="participation",
            text=f"参加申請が届きました：「{post.title}」",
            url="/?tab=messages",
        )

    return JsonResponse({"ok": True, "conversation_id": convo.id})


# =========================
# 閲覧ログ（人気順の材料）
# =========================
@login_required
def post_viewlog(request, pk):
    post = get_object_or_404(Post, pk=pk)
    PostView.objects.create(post=post, user=request.user)
    return JsonResponse({"ok": True})


# =========================
# 通知
# =========================
@login_required
def notifications_list(request):
    items = Notification.objects.filter(user=request.user).order_by("-created_at")[:100]
    data = []
    for n in items:
        data.append({
            "id": n.id,
            "notif_type": n.notif_type,
            "text": n.text,
            "url": n.url,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%m/%d %H:%M"),
        })
    return JsonResponse({"ok": True, "notifications": data})


@login_required
def notifications_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


# =========================
# メッセージ（JSON API）
# =========================
@login_required
def messages_thread(request, conversation_id):
    convo = get_object_or_404(Conversation, id=conversation_id)
    if not convo.participants.filter(id=request.user.id).exists():
        return JsonResponse({"ok": False})

    # 既読更新
    read, _ = MessageRead.objects.get_or_create(conversation=convo, user=request.user)
    read.last_read_at = timezone.now()
    read.save()

    msgs = convo.messages.select_related("sender").order_by("created_at")[:300]
    data = []
    for m in msgs:
        data.append({
            "id": m.id,
            "body": m.body,
            "created_at": m.created_at.strftime("%m/%d %H:%M"),
            "sender_name": m.sender.profile.display_name if hasattr(m.sender, "profile") and m.sender.profile.display_name else m.sender.username,
            "is_me": m.sender_id == request.user.id,
        })

    title = convo.title or _conversation_title_fallback(convo, request.user)
    return JsonResponse({"ok": True, "conversation": {"id": convo.id, "title": title}, "messages": data})


@login_required
def messages_send(request, conversation_id):
    convo = get_object_or_404(Conversation, id=conversation_id)
    if not convo.participants.filter(id=request.user.id).exists():
        return JsonResponse({"ok": False})

    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"ok": False})

    Message.objects.create(conversation=convo, sender=request.user, body=body)
    convo.updated_at = timezone.now()
    convo.save()

    # 相手へ通知
    for u in convo.participants.exclude(id=request.user.id):
        Notification.objects.create(
            user=u,
            notif_type="message",
            text="新しいメッセージが届きました",
            url="/?tab=messages",
        )

    return JsonResponse({"ok": True})

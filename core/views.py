from django.contrib.auth import login 
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
)

# -------------------------
# App（単一画面）
# -------------------------
def app(request):
    tab = request.GET.get("tab") or "home"

    # 予期しない tab を弾く（事故防止）
    allowed_tabs = {"home", "search", "create", "messages", "profile", "profile_edit"}
    if tab not in allowed_tabs:
        tab = "home"

    # HOME: posts
    posts_qs = (
        Post.objects.all()
        .select_related("author")
        .prefetch_related("tags")
        .annotate(
            favs_count=Count("favorites", distinct=True),
            views_count=Count("views", distinct=True),
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

    # -------------------------
    # SEARCH
    # -------------------------
    search_query = (request.GET.get("q", "") or "").strip()
    category = request.GET.get("category", "")
    tag = request.GET.get("tag", "")
    only_open = request.GET.get("open") == "1"

    # ① 投稿検索（既存）
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

    # ② サークル（プロフィール）検索（←今回追加したいのはこれ）
    circle_results = Circle.objects.none()
    if search_query:
        circle_results = (
            Circle.objects
            .filter(name__icontains=search_query)
            .exclude(name="")
            .order_by("name")[:50]
        )

    selected_circle = None
    circle_id = request.GET.get("circle_id")
    if circle_id:
        try:
            selected_circle = Circle.objects.filter(id=circle_id).first()
        except Circle.DoesNotExist:
            selected_circle = None





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

    # プロフィール編集用フォーム
    profile_form = None

    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        circle, _ = Circle.objects.get_or_create(owner=request.user)

        my_posts = (
            Post.objects.filter(author=request.user)
            .annotate(
                favs_count=Count("favorites", distinct=True),
                views_count=Count("views", distinct=True),
            )
            .order_by("-created_at")[:50]
        )

        saved_posts = (
            Post.objects.filter(favorites=request.user)
            .annotate(
                favs_count=Count("favorites", distinct=True),
                views_count=Count("views", distinct=True),
            )
            .order_by("-created_at")[:50]
        )

        unread_notifs = Notification.objects.filter(user=request.user, is_read=False).count()

        # conversations list
        convo_qs = (
            Conversation.objects.filter(participants=request.user)
            .prefetch_related("participants", "messages")
            .order_by("-updated_at")[:50]
        )
        for c in convo_qs:
            last = c.messages.order_by("-created_at").first()
            last_text = last.body if last else ""
            read = MessageRead.objects.filter(conversation=c, user=request.user).first()
            last_read_at = read.last_read_at if read else timezone.make_aware(timezone.datetime.min)
            unread = c.messages.filter(created_at__gt=last_read_at).exclude(sender=request.user).count()

            conversations.append(
                {
                    "id": c.id,
                    "title": c.title or f"Conversation {c.id}",
                    "last_message": last_text,
                    "unread": unread,
                }
            )

        # -------------------------
        # Profile Edit
        # /?tab=profile_edit
        # -------------------------
        if tab == "profile_edit":
            if request.method == "POST":
                profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
                if profile_form.is_valid():
                    profile_form.save()
                    Notification.objects.create(
                        user=request.user,
                        notif_type="participation",
                        text="プロフィールを更新しました",
                        url="/?tab=profile",
                    )
                    return redirect("/?tab=profile")
            else:
                profile_form = ProfileForm(instance=profile)

    # ログインしてないのに profile_edit を開いたら login に飛ばす
    if tab == "profile_edit" and not request.user.is_authenticated:
        return redirect("login")
    

    ctx = {
        "initial_tab": tab,
        "posts": posts,
        "sort": sort,

        "search_query": search_query,
        "circle_results": circle_results,
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

        "profile_form": profile_form,
        "selected_circle": selected_circle,
    }
    return render(request, "core/app.html", ctx)


def profile_detail_json(request, pk):
    profile = get_object_or_404(Profile, pk=pk)

    data = {
        "id": profile.id,
        "circle_name": profile.circle_name,
        "bio": profile.bio,
        "place": profile.place,
        "frequency": profile.frequency,
    }
    return JsonResponse(data)

# -------------------------
# Post: detail JSON + view count
# -------------------------
def post_detail_json(request, pk):
    p = get_object_or_404(Post.objects.prefetch_related("tags").select_related("author"), pk=pk)

    seen = request.session.get("seen_posts", [])
    if pk not in seen:
        PostView.objects.create(post=p, user=request.user if request.user.is_authenticated else None)
        seen.append(pk)
        request.session["seen_posts"] = seen

    data = {
        "id": p.id,
        "title": p.title,
        "circle_name": p.circle_name,
        "place": p.place,
        "detail": p.detail,
        "event_at": p.event_at.strftime("%Y/%m/%d %H:%M"),
        "status": p.effective_status,
        "category": p.category,
        "tags": [t.name for t in p.tags.all()],
        "image_url": p.image.url if p.image else None,
        "is_owner": (request.user.is_authenticated and p.author_id == request.user.id),
        "can_fav": request.user.is_authenticated,
    }
    return JsonResponse(data)


# -------------------------
# Post: create/edit/delete
# -------------------------
@login_required
def post_create(request):
    if request.method == "POST":
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            p = form.save(commit=False)
            p.author = request.user

            if not p.circle_name:
                circle = getattr(request.user, "circle", None)
                if circle and circle.name:
                    p.circle_name = circle.name

            p.save()

            tag_names = form.cleaned_data.get("tags", [])
            tag_objs = []
            for name in tag_names:
                t, _ = Tag.objects.get_or_create(name=name)
                tag_objs.append(t)
            if tag_objs:
                p.tags.set(tag_objs)

            Notification.objects.create(
                user=request.user,
                notif_type="participation",
                text=f"投稿を作成しました: {p.title}",
                url="/?tab=home",
            )
            return redirect("/?tab=home")
    else:
        form = PostCreateForm()

    return render(request, "core/app.html", {"initial_tab": "create", "post_form": form})


@login_required
def post_edit(request, pk):
    p = get_object_or_404(Post, pk=pk)
    if p.author_id != request.user.id:
        return HttpResponseForbidden("Not allowed")

    if request.method == "POST":
        form = PostCreateForm(request.POST, request.FILES, instance=p)
        if form.is_valid():
            p = form.save()
            tag_names = form.cleaned_data.get("tags", [])
            tag_objs = []
            for name in tag_names:
                t, _ = Tag.objects.get_or_create(name=name)
                tag_objs.append(t)
            p.tags.set(tag_objs)
            return redirect("/?tab=home")
    else:
        init = {"tags": ", ".join([t.name for t in p.tags.all()])}
        form = PostCreateForm(instance=p, initial=init)

    return render(request, "core/app.html", {"initial_tab": "home", "edit_form": form, "edit_post_id": p.id})


@login_required
@require_POST
def post_delete(request, pk):
    p = get_object_or_404(Post, pk=pk)
    if p.author_id != request.user.id:
        return HttpResponseForbidden("Not allowed")
    p.delete()
    return redirect("/?tab=home")


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
# Profile / Circle save（既存のまま）
# -------------------------
@login_required
@require_POST
def profile_save(request):
    circle, _ = Circle.objects.get_or_create(owner=request.user)
    form = CircleForm(request.POST, request.FILES, instance=circle)

    if form.is_valid():
        form.save()
        return redirect("/?tab=profile")

    return render(
        request,
        "core/app.html",
        {
            "initial_tab": "profile",
            "circle": circle,
            "circle_form": form,
        }
    )


# -------------------------
# Messages（DM）
# -------------------------
@login_required
def start_conversation(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    me = request.user
    other = post.author
    if me.id == other.id:
        return redirect("/?tab=messages")

    existing = (
        Conversation.objects.filter(post=post, is_group=False, participants=me)
        .filter(participants=other)
        .first()
    )
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

    read, _ = MessageRead.objects.get_or_create(conversation=convo, user=request.user)
    read.last_read_at = timezone.now()
    read.save(update_fields=["last_read_at"])

    return JsonResponse(
        {
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
            ],
        }
    )


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
    return JsonResponse(
        {
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
            ],
        }
    )


@login_required
@require_POST
def notifications_mark_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("core:app")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
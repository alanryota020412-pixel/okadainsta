from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

User = settings.AUTH_USER_MODEL


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=50, blank=True)
    school_year = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    circle_name = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")  # 活動内容
    place = models.CharField(max_length=120, blank=True, default="")
    frequency = models.CharField(max_length=60, blank=True, default="")
    x_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")

    stats_posts = models.PositiveIntegerField(default=0)
    stats_favs = models.PositiveIntegerField(default=0)
    stats_msgs = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.display_name or f"profile:{self.user_id}"

def circle_icon_path(instance, filename):
    return f"circles/{instance.id}/icon/{filename}"

def circle_cover_path(instance, filename):
    return f"circles/{instance.id}/cover/{filename}"

class Circle(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="circle")

    name = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True)
    icon_image = models.ImageField(upload_to=circle_icon_path, blank=True, null=True)
    cover_image = models.ImageField(upload_to=circle_cover_path, blank=True, null=True)
    bio = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to="circle_avatars/", blank=True, null=True)

    place = models.CharField(max_length=100, blank=True, default="")

    FREQ_CHOICES = [
        ("weekly1", "週1回"),
        ("weekly2", "週2回"),
        ("weekly3", "週3回"),
        ("monthly", "月数回"),
        ("irregular", "不定期"),
    ]
    frequency = models.CharField(max_length=20, choices=FREQ_CHOICES, blank=True, default="weekly2")

    x_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")

    def __str__(self):
        return self.name or f"circle:{self.owner_id}"


class Tag(models.Model):
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    STATUS_CHOICES = [
        ("open", "募集中"),
        ("closed", "終了"),
    ]
    CATEGORY_CHOICES = [
        ("sports", "スポーツ"),
        ("music", "音楽"),
        ("culture", "文化/趣味"),
        ("volunteer", "ボランティア"),
        ("it", "IT/開発"),
        ("study", "勉強/ゼミ"),
        ("other", "その他"),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=120)
    circle_name = models.CharField(max_length=80, blank=True)
    place = models.CharField(max_length=120, blank=True)
    detail = models.TextField(blank=True)
    event_at = models.DateTimeField()
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    body = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    created_at = models.DateTimeField(default=timezone.now)

    favorites = models.ManyToManyField(User, blank=True, related_name="favorite_posts", through="Favorite")

    @property
    def is_ended(self):
        return self.event_at < timezone.now()

    @property
    def effective_status(self):
        # 自動終了：event_at 過ぎたら closed 扱い
        if self.is_ended:
            return "closed"
        return self.status

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not (self.circle_name or "").strip():
            name = ""

            # 1) Profile.display_name 優先
            if self.author_id and hasattr(self.author, "profile"):
                name = (self.author.profile.display_name or "").strip()

            # 2) ダメなら Circle.name
            if not name and self.author_id and hasattr(self.author, "circle"):
                name = (self.author.circle.name or "").strip()

            # 3) それもダメなら username
            if not name and self.author_id:
                name = (self.author.username or "").strip()

            if name:
                self.circle_name = name

        super().save(*args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "post")]


class Participation(models.Model):
    STATUS = [
        ("pending", "申請中"),
        ("approved", "承認"),
        ("rejected", "却下"),
        ("canceled", "キャンセル"),
    ]
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="participations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="participations")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("post", "user")]


class Conversation(models.Model):
    # DM/グループ両対応
    title = models.CharField(max_length=120, blank=True)
    participants = models.ManyToManyField(User, related_name="conversations")
    is_group = models.BooleanField(default=False)

    # 「この投稿のやりとり」などに使う（任意）
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")

    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title or f"convo:{self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"msg:{self.id}"


class MessageRead(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("conversation", "user")]


class Notification(models.Model):
    TYPE = [
        ("favorite", "お気に入り"),
        ("participation", "参加申請"),
        ("message", "メッセージ"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notif_type = models.CharField(max_length=20, choices=TYPE)
    text = models.CharField(max_length=200)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)


class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["post", "viewed_at"])]

# プロフィールとサークルのDB作成機能

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

UserModel = get_user_model()

@receiver(post_save, sender=UserModel)
def create_profile_and_circle(sender, instance, created, **kwargs):
    if not created:
        return

    # Profileを作って display_name を初期化（username から仮置き）
    p, _ = Profile.objects.get_or_create(user=instance)
    if not (p.display_name or "").strip():
        p.display_name = instance.username  # ← emailログインならここ変える
        p.save()

    # Circleも必要なら作る（ただし投稿の補完はProfile基準にしたので必須ではない）
    Circle.objects.get_or_create(owner=instance)

class PostImage(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="posts/")
    created_at = models.DateTimeField(auto_now_add=True)


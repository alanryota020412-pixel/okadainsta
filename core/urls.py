from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # ===== アプリ入口（単一画面）=====
    path("", views.app, name="app"),

    # ===== Posts =====
    path("posts/create/", views.post_create, name="post_create"),
    path("posts/<int:pk>/edit/", views.post_edit, name="post_edit"),
    path("posts/<int:pk>/delete/", views.post_delete, name="post_delete"),

    # Favorite（views.py は toggle_favorite / 引数は pk）
    path("posts/<int:pk>/favorite/", views.toggle_favorite, name="post_toggle_favorite"),

    # Post detail（JSON）
    path("posts/<int:pk>/json/", views.post_detail_json, name="post_detail_json"),

    # ===== Profile / Circle 保存 =====
    path("profile/save/", views.profile_save, name="profile_save"),

    # ===== Messages =====
    path("posts/<int:post_id>/dm/start/", views.start_conversation, name="start_conversation"),
    path("messages/<int:convo_id>/json/", views.conversation_json, name="conversation_json"),
    path("messages/<int:convo_id>/send/", views.send_message, name="send_message"),

    # ===== Notifications =====
    path("notifications/json/", views.notifications_json, name="notifications_json"),
    path("notifications/mark-read/", views.notifications_mark_read, name="notifications_mark_read"),
]

# core/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "core"

urlpatterns = [
    path("", views.app, name="app"),

    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("post/create/", views.post_create, name="post_create"),
    path("post/<int:pk>/edit/", views.post_edit, name="post_edit"),
    path("post/<int:pk>/delete/", views.post_delete, name="post_delete"),

    # ✅ これが無いとプロフィール保存が効かない
    path("profile/update/", views.profile_update, name="profile_update"),
    path("circle/update/", views.circle_update, name="circle_update"),

    # ajax
    path("post/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("post/<int:pk>/apply/", views.apply_post, name="apply_post"),
    path("post/<int:pk>/viewlog/", views.post_viewlog, name="post_viewlog"),

    path("notifications/", views.notifications_list, name="notifications_list"),
    path("notifications/read/", views.notifications_read_all, name="notifications_read_all"),

    path("messages/<int:conversation_id>/", views.messages_thread, name="messages_thread"),
    path("messages/<int:conversation_id>/send/", views.messages_send, name="messages_send"),

    path("profile/update/", views.profile_update, name="profile_update"),
    path("circle/update/", views.circle_update, name="circle_update"),
]

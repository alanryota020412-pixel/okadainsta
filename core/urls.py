from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("profile/save/", views.profile_save, name="profile_save"),
    path("post/create/", views.post_create, name="post_create"),
]

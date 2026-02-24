from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),

    # allauth
    path("accounts/", include("allauth.urls")),

    # 独自 accounts アプリ
    path("accounts/", include("accounts.urls")),

    # /login → allauth の login へ
    path(
        "login/",
        RedirectView.as_view(pattern_name="account_login", permanent=True),
    ),

    # core app
    path("", include(("core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
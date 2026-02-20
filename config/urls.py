from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')), 
    path('login/', RedirectView.as_view(pattern_name='account_login', permanent=True)), # 追加
    path("", include(("core.urls", "core"), namespace="core")),
]

# 開発中だけ media 配信
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

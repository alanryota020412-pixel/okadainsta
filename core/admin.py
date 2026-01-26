from django.contrib import admin
from .models import Post

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "circle_name", "event_at", "created_at")
    search_fields = ("title", "circle_name", "location")
    list_filter = ("created_at",)

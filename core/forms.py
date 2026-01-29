from django import forms
from .models import Profile, Circle, Post


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "school_year", "role", "bio", "avatar"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


class CircleForm(forms.ModelForm):
    class Meta:
        model = Circle
        fields = ["name", "activity_days", "members_count", "sns_link", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class PostCreateForm(forms.ModelForm):
    tags = forms.CharField(required=False)  # カンマ区切り

    class Meta:
        model = Post
        fields = ["image", "title", "circle_name", "event_at", "place", "category", "status", "detail"]
        widgets = {
            "event_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "detail": forms.Textarea(attrs={"rows": 5}),
        }

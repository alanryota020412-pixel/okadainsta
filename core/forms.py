from django import forms
from .models import Post, Profile, Circle


class PostCreateForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["image", "title", "circle_name", "event_at", "place", "detail", "status"]

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and img.size > 5 * 1024 * 1024:
            raise forms.ValidationError("画像サイズは5MB以下にしてください。")
        return img


class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "circle_name", "event_at", "place", "detail", "status"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "school_year", "role", "bio", "avatar"]


class CircleForm(forms.ModelForm):
    class Meta:
        model = Circle
        fields = ["name", "activity_days", "members_count", "sns_link", "description"]

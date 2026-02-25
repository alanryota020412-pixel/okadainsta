from django import forms
from .models import Profile, Circle, Post

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar",
                  "circle_name",
                  "description",
                  "place",
                  "frequency",
                  "x_url",
                  "instagram_url",]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

class CircleForm(forms.ModelForm):
    class Meta:
        model = Circle
        fields = ["avatar", "name", "bio", "place", "frequency", "x_url", "instagram_url", "cover_image",]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

class PostCreateForm(forms.ModelForm):
    # タグ入力（カンマ区切り）
    tags = forms.CharField(required=False)

    class Meta:
        model = Post
        fields = [
            "image",
            "title",
            "circle_name",
            "event_at",
            "place",
            "detail",
            "status",
            "category",
        ]

    def clean_tags(self):
        raw = self.cleaned_data.get("tags", "")
        # 例: "新歓, 初心者歓迎" → ["新歓","初心者歓迎"]
        items = [t.strip() for t in raw.split(",") if t.strip()]
        # 重複除去（順序維持）
        seen = set()
        out = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

class CircleEditForm(forms.ModelForm):
    class Meta:
        model = Circle
        fields = ["name", "description", "icon_image", "cover_image"]
        widgets = {
            "icon_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "cover_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
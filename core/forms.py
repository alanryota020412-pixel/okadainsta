from django import forms
from .models import Profile, Circle, Post

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "school_year", "role", "bio", "avatar"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

class CircleForm(forms.ModelForm):
    class Meta:
        model = Circle
        fields = ["name", "activity_days", "members_count", "sns_link", "description"]
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

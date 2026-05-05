from django import forms
from .models import CommunityPost, CommunityComment


class CommunityPostForm(forms.ModelForm):
    class Meta:
        model = CommunityPost
        fields = (
            "category",
            "title",
            "content",
            "image",
        )

        widgets = {
            "category": forms.Select(
                attrs={
                    "class": "community-input",
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "community-input",
                    "placeholder": "제목을 입력하세요.",
                    "maxlength": "120",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "community-textarea",
                    "placeholder": "여행 이야기, 질문, 꿀팁, 동행 모집글 등을 자유롭게 작성해보세요.",
                    "rows": 12,
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "community-file",
                    "accept": "image/*",
                }
            ),
        }

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()

        if len(title) < 2:
            raise forms.ValidationError("제목은 2자 이상 입력해주세요.")

        return title

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()

        if len(content) < 5:
            raise forms.ValidationError("내용은 5자 이상 입력해주세요.")

        return content


class CommunityCommentForm(forms.ModelForm):
    class Meta:
        model = CommunityComment
        fields = (
            "content",
        )

        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "community-comment-textarea",
                    "placeholder": "댓글을 입력하세요.",
                    "rows": 3,
                }
            ),
        }

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()

        if len(content) < 1:
            raise forms.ValidationError("댓글 내용을 입력해주세요.")

        return content
from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import AuctionRequest, AuctionAnswer


MIN_REWARD_POINTS = 100
MAX_REWARD_POINTS = 1_000_000


class AuctionRequestForm(forms.ModelForm):
    deadline_days = forms.ChoiceField(
        label="마감 기간",
        choices=[
            ("1", "1일"),
            ("3", "3일"),
            ("7", "7일"),
        ],
        initial="3",
        widget=forms.Select,
    )

    class Meta:
        model = AuctionRequest
        fields = (
            "title",
            "start_area",
            "destination",
            "travel_date",
            "people_count",
            "transport",
            "budget",
            "request_detail",
            "reward_points",
            "deadline_days",
        )

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 인천 출발 강릉 당일치기 코스 짜주세요",
                }
            ),
            "start_area": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 인천 청라",
                }
            ),
            "destination": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 강릉",
                }
            ),
            "travel_date": forms.DateInput(
                attrs={
                    "class": "auction-input",
                    "type": "date",
                }
            ),
            "people_count": forms.NumberInput(
                attrs={
                    "class": "auction-input",
                    "min": "1",
                    "max": "20",
                }
            ),
            "transport": forms.Select(
                attrs={
                    "class": "auction-select",
                }
            ),
            "budget": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 총 20만원, 1인 5만원",
                }
            ),
            "request_detail": forms.Textarea(
                attrs={
                    "class": "auction-textarea",
                    "rows": 8,
                    "placeholder": "원하는 여행 스타일, 꼭 가고 싶은 곳, 피하고 싶은 코스 등을 자세히 적어주세요.",
                }
            ),
            "reward_points": forms.NumberInput(
                attrs={
                    "class": "auction-input",
                    "min": str(MIN_REWARD_POINTS),
                    "max": str(MAX_REWARD_POINTS),
                    "step": "10",
                    "placeholder": "예: 500",
                }
            ),
        }

    def clean_reward_points(self):
        points = self.cleaned_data.get("reward_points") or 0

        if points < MIN_REWARD_POINTS:
            raise forms.ValidationError(f"보상 포인트는 최소 {MIN_REWARD_POINTS}P 이상이어야 합니다.")

        if points > MAX_REWARD_POINTS:
            raise forms.ValidationError(f"보상 포인트는 최대 {MAX_REWARD_POINTS:,}P까지 가능합니다.")

        return points

    def clean_deadline_days(self):
        value = self.cleaned_data.get("deadline_days")

        try:
            days = int(value)
        except (TypeError, ValueError):
            raise forms.ValidationError("마감 기간을 선택해주세요.")

        if days not in [1, 3, 7]:
            raise forms.ValidationError("올바른 마감 기간을 선택해주세요.")

        return days

    def save(self, commit=True):
        instance = super().save(commit=False)
        deadline_days = self.cleaned_data.get("deadline_days") or 3
        instance.deadline_at = timezone.now() + timedelta(days=deadline_days)

        if commit:
            instance.save()

        return instance


class AuctionAnswerForm(forms.ModelForm):
    class Meta:
        model = AuctionAnswer
        fields = (
            "title",
            "summary",
            "total_time",
            "total_cost",
            "content",
        )

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 강릉 바다+맛집 당일치기 코스",
                }
            ),
            "summary": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 자차 기준, 바다와 맛집 중심의 무리 없는 코스",
                }
            ),
            "total_time": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 약 10시간",
                }
            ),
            "total_cost": forms.TextInput(
                attrs={
                    "class": "auction-input",
                    "placeholder": "예: 2인 약 12만원",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "auction-textarea",
                    "rows": 10,
                    "placeholder": "시간대별 일정, 이동 팁, 추천 이유를 자세히 작성해주세요.",
                }
            ),
        }

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()

        if len(content) < 80:
            raise forms.ValidationError("상세 코스는 최소 80자 이상 작성해주세요.")

        return content
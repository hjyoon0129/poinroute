from django import forms
from django.forms import inlineformset_factory

from .models import Post, Place


DAY_CHOICES = [(i, f"{i}일차") for i in range(1, 11)]

TIME_CHOICES = [('', '방문 시간 선택')]
for ampm in ['오전', '오후']:
    for h in [12] + list(range(1, 12)):
        for m in ['00', '30']:
            TIME_CHOICES.append((f"{ampm} {h:02d}:{m}", f"{ampm} {h:02d}:{m}"))

START_TIME_CHOICES = [('', '출발 시간 선택')]
for ampm in ['오전', '오후']:
    for h in [12] + list(range(1, 12)):
        for m in ['00', '30']:
            START_TIME_CHOICES.append((f"{ampm} {h:02d}:{m}", f"{ampm} {h:02d}:{m}"))


class PostForm(forms.ModelForm):
    start_time = forms.ChoiceField(
        choices=START_TIME_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'custom-select'})
    )

    class Meta:
        model = Post
        fields = [
            'theme',
            'title',
            'thumbnail',

            'start_region',
            'start_district',
            'start_neighborhood',
            'start_time',

            'start_place_name',
            'start_latitude',
            'start_longitude',

            'destination',
            'travel_start_date',
            'travel_end_date',

            'total_cost',
            'total_time',
        ]

        widgets = {
            'theme': forms.Select(attrs={
                'class': 'custom-select',
            }),

            'title': forms.TextInput(attrs={
                'class': 'form-input-clean',
                'placeholder': '코스 제목을 입력해주세요',
            }),

            'thumbnail': forms.ClearableFileInput(attrs={
                'class': 'thumbnail-upload-input',
                'accept': 'image/*',
            }),

            'start_region': forms.HiddenInput(attrs={
                'id': 'id_start_region',
            }),

            'start_district': forms.HiddenInput(attrs={
                'id': 'id_start_district',
            }),

            'start_neighborhood': forms.HiddenInput(attrs={
                'id': 'id_start_neighborhood',
            }),

            'start_place_name': forms.HiddenInput(attrs={
                'id': 'id_start_place_name',
            }),

            'start_latitude': forms.HiddenInput(attrs={
                'id': 'id_start_latitude',
            }),

            'start_longitude': forms.HiddenInput(attrs={
                'id': 'id_start_longitude',
            }),

            'destination': forms.TextInput(attrs={
                'class': 'form-input-clean',
                'placeholder': '도착지 예: 강릉, 부산, 제주',
            }),

            'travel_start_date': forms.TextInput(attrs={
                'class': 'form-input-clean date-picker',
                'placeholder': '여행 시작일',
            }),

            'travel_end_date': forms.TextInput(attrs={
                'class': 'form-input-clean date-picker',
                'placeholder': '여행 종료일',
            }),

            'total_cost': forms.HiddenInput(attrs={
                'id': 'id_total_cost',
            }),

            'total_time': forms.HiddenInput(attrs={
                'id': 'id_total_time',
            }),
        }


class PlaceForm(forms.ModelForm):
    day = forms.ChoiceField(
        choices=DAY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'custom-select place-day',
        }),
        initial=1
    )

    visit_time_str = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={
            'class': 'custom-select place-time',
        }),
        required=False
    )

    class Meta:
        model = Place
        fields = [
            'day',
            'visit_time_str',
            'place_name',
            'latitude',
            'longitude',
            'cost',
            'description',
            'image',
        ]

        widgets = {
            'place_name': forms.TextInput(attrs={
                'class': 'form-input-clean place-name-input',
                'placeholder': '장소 이름 (지도 검색으로 선택)',
                'readonly': 'readonly',
            }),

            'latitude': forms.HiddenInput(attrs={
                'class': 'place-lat',
            }),

            'longitude': forms.HiddenInput(attrs={
                'class': 'place-lng',
            }),

            'cost': forms.NumberInput(attrs={
                'class': 'form-input-clean place-cost',
                'placeholder': '0',
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-input-clean',
                'rows': 4,
                'placeholder': '이 장소의 포인트, 팁, 추천 이유를 적어주세요',
            }),

            'image': forms.ClearableFileInput(attrs={
                'class': 'form-input-clean place-image-input',
                'accept': 'image/*',
            }),
        }


PlaceFormSet = inlineformset_factory(
    Post,
    Place,
    form=PlaceForm,
    extra=3,
    can_delete=True
)
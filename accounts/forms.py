import re

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Profile


User = get_user_model()


class LoginForm(forms.Form):
    login_id = forms.CharField(
        label="아이디 또는 보호 이메일",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "아이디 또는 보호 이메일 입력",
                "autocomplete": "username",
            }
        ),
    )

    pin = forms.CharField(
        label="6자리 핀번호",
        min_length=6,
        max_length=6,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "숫자 6자리",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autocomplete": "current-password",
            }
        ),
    )

    def clean_login_id(self):
        login_id = self.cleaned_data.get("login_id", "").strip()

        if not login_id:
            raise forms.ValidationError("아이디 또는 보호 이메일을 입력해주세요.")

        return login_id

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "").strip()

        if not pin.isdigit() or len(pin) != 6:
            raise forms.ValidationError("핀번호는 숫자 6자리여야 합니다.")

        return pin


class SignupForm(forms.Form):
    login_id = forms.CharField(
        label="아이디",
        min_length=4,
        max_length=24,
        widget=forms.TextInput(
            attrs={
                "placeholder": "영문, 숫자, _ 조합 4~24자",
                "autocomplete": "username",
            }
        ),
    )

    recovery_email = forms.EmailField(
        label="보호 이메일",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "비밀번호 찾기용 이메일",
                "autocomplete": "email",
            }
        ),
    )

    pin = forms.CharField(
        label="6자리 핀번호",
        min_length=6,
        max_length=6,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "숫자 6자리",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autocomplete": "new-password",
            }
        ),
    )

    pin_confirm = forms.CharField(
        label="핀번호 확인",
        min_length=6,
        max_length=6,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "핀번호 다시 입력",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autocomplete": "new-password",
            }
        ),
    )

    agree_terms = forms.BooleanField(
        label="약관 동의",
        required=True,
    )

    def clean_login_id(self):
        login_id = self.cleaned_data.get("login_id", "").strip()

        if not login_id:
            raise forms.ValidationError("아이디를 입력해주세요.")

        if not re.match(r"^[a-zA-Z0-9_]{4,24}$", login_id):
            raise forms.ValidationError("아이디는 영문, 숫자, _ 조합 4~24자로 입력해주세요.")

        if User.objects.filter(username__iexact=login_id).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")

        return login_id

    def clean_recovery_email(self):
        email = self.cleaned_data.get("recovery_email", "").strip().lower()

        if not email:
            raise forms.ValidationError("보호 이메일을 입력해주세요.")

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("이미 사용 중인 이메일입니다.")

        if Profile.objects.filter(recovery_email__iexact=email).exists():
            raise forms.ValidationError("이미 사용 중인 보호 이메일입니다.")

        return email

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "").strip()

        if not pin.isdigit() or len(pin) != 6:
            raise forms.ValidationError("핀번호는 숫자 6자리여야 합니다.")

        return pin

    def clean_pin_confirm(self):
        pin_confirm = self.cleaned_data.get("pin_confirm", "").strip()

        if not pin_confirm.isdigit() or len(pin_confirm) != 6:
            raise forms.ValidationError("핀번호 확인은 숫자 6자리여야 합니다.")

        return pin_confirm

    def clean(self):
        cleaned_data = super().clean()

        pin = cleaned_data.get("pin")
        pin_confirm = cleaned_data.get("pin_confirm")

        if pin and pin_confirm and pin != pin_confirm:
            raise forms.ValidationError("핀번호가 서로 일치하지 않습니다.")

        return cleaned_data

    def save(self):
        login_id = self.cleaned_data["login_id"].strip()
        recovery_email = self.cleaned_data["recovery_email"].strip().lower()
        pin = self.cleaned_data["pin"].strip()

        with transaction.atomic():
            user = User.objects.create_user(
                username=login_id,
                email=recovery_email,
                password=pin,
            )

            profile, _ = Profile.objects.get_or_create(user=user)

            profile.recovery_email = recovery_email

            # 중요:
            # 회원가입 직후 닉네임 모달이 뜨려면 nickname은 반드시 빈 값이어야 한다.
            # 아이디나 이메일 앞부분을 닉네임으로 자동 저장하지 않는다.
            profile.nickname = ""

            update_fields = [
                "recovery_email",
                "nickname",
                "updated_at",
            ]

            profile.save(update_fields=update_fields)

        return user


class NicknameForm(forms.Form):
    nickname = forms.CharField(
        label="닉네임",
        min_length=2,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "예: 청라여행자",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_nickname(self):
        nickname = self.cleaned_data.get("nickname", "").strip()

        if not nickname:
            raise forms.ValidationError("닉네임을 입력해주세요.")

        if len(nickname) < 2:
            raise forms.ValidationError("닉네임은 2자 이상이어야 합니다.")

        if len(nickname) > 20:
            raise forms.ValidationError("닉네임은 20자 이하로 입력해주세요.")

        if not re.match(r"^[가-힣a-zA-Z0-9_]{2,20}$", nickname):
            raise forms.ValidationError("닉네임은 한글, 영문, 숫자, _ 만 사용할 수 있습니다.")

        qs = Profile.objects.filter(nickname__iexact=nickname)

        if self.user:
            qs = qs.exclude(user=self.user)

        if qs.exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")

        return nickname
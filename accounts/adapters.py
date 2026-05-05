import re
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse

from .models import Profile


User = get_user_model()


def get_profile_field_names():
    return {field.name for field in Profile._meta.get_fields()}


def make_safe_base(value):
    value = value or ""
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")

    if not value:
        value = "poinroute_user"

    return value[:24]


def make_unique_username(email="", name="", provider="", uid=""):
    """
    소셜 계정으로 처음 들어온 사용자의 username 자동 생성.

    우선순위:
    1. 이메일 앞부분
    2. 소셜 이름/닉네임
    3. provider + uid
    4. poinroute_user

    카카오는 이메일 권한이 없을 수 있으므로 provider/uid 기반 생성이 중요하다.
    """
    if email:
        base = email.split("@")[0]
    elif name:
        base = name
    elif provider and uid:
        base = f"{provider}_{uid}"
    else:
        base = "poinroute_user"

    base = make_safe_base(base)

    username = base
    index = 1

    while User.objects.filter(username__iexact=username).exists():
        suffix = str(index)
        username = f"{base[:24 - len(suffix)]}{suffix}"
        index += 1

    return username


def extract_social_email(sociallogin, data):
    """
    provider별 이메일 추출.
    카카오는 이메일 권한이 없으면 빈 값일 수 있음.
    """
    data = data or {}
    extra_data = sociallogin.account.extra_data or {}
    provider = sociallogin.account.provider

    email = data.get("email") or ""

    if email:
        return email

    if provider == "kakao":
        kakao_account = extra_data.get("kakao_account") or {}
        return kakao_account.get("email") or ""

    if provider == "naver":
        response = extra_data.get("response") or {}
        return response.get("email") or ""

    if provider == "google":
        return extra_data.get("email") or ""

    return ""


def extract_social_name(sociallogin, data):
    """
    provider별 표시 이름/닉네임 추출.
    단, 이 값은 username 생성용으로만 쓰고 Profile.nickname에는 저장하지 않는다.
    """
    data = data or {}
    extra_data = sociallogin.account.extra_data or {}
    provider = sociallogin.account.provider

    name = (
        data.get("name")
        or data.get("username")
        or data.get("first_name")
        or ""
    )

    if provider == "kakao":
        properties = extra_data.get("properties") or {}
        kakao_account = extra_data.get("kakao_account") or {}
        kakao_profile = kakao_account.get("profile") or {}

        return (
            properties.get("nickname")
            or kakao_profile.get("nickname")
            or name
            or "kakao"
        )

    if provider == "naver":
        response = extra_data.get("response") or {}

        return (
            response.get("nickname")
            or response.get("name")
            or name
            or "naver"
        )

    if provider == "google":
        return (
            extra_data.get("name")
            or extra_data.get("given_name")
            or name
            or "google"
        )

    return name


def get_posts_list_url():
    """
    닉네임이 없는 유저를 반드시 base.html을 상속하는 루트 목록으로 보낸다.
    여기에 가야 base.html의 닉네임 모달이 뜬다.
    """
    try:
        return reverse("posts:list")
    except NoReverseMatch:
        return "/"


def get_nickname_required_url():
    base_url = get_posts_list_url()
    query = urlencode({"nickname": "1"})
    return f"{base_url}?{query}"


def get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def safe_save_profile(profile, update_fields):
    field_names = get_profile_field_names()

    final_fields = []

    for field in update_fields:
        if field in field_names:
            final_fields.append(field)

    if "updated_at" in field_names and "updated_at" not in final_fields:
        final_fields.append("updated_at")

    if final_fields:
        profile.save(update_fields=list(dict.fromkeys(final_fields)))
    else:
        profile.save()


def user_needs_nickname(user):
    if not user or not user.is_authenticated:
        return False

    profile = get_or_create_profile(user)
    nickname = getattr(profile, "nickname", "") or ""

    return not bool(nickname.strip())


def sync_profile_email_without_nickname(user):
    """
    소셜 로그인 후 프로필은 만들되 닉네임은 절대 자동 저장하지 않는다.

    중요:
    - 닉네임이 비어 있어야 base.html의 닉네임 모달이 뜬다.
    - 기존에 사용자가 직접 설정한 닉네임은 절대 지우지 않는다.
    """
    profile = get_or_create_profile(user)
    field_names = get_profile_field_names()

    update_fields = []

    if (
        "recovery_email" in field_names
        and getattr(user, "email", "")
        and not getattr(profile, "recovery_email", "")
    ):
        profile.recovery_email = user.email
        update_fields.append("recovery_email")

    if "nickname" in field_names and getattr(profile, "nickname", None) is None:
        profile.nickname = ""
        update_fields.append("nickname")

    if "points" in field_names and getattr(profile, "points", None) is None:
        profile.points = 0
        update_fields.append("points")

    if (
        "total_earned_points" in field_names
        and getattr(profile, "total_earned_points", None) is None
    ):
        profile.total_earned_points = 0
        update_fields.append("total_earned_points")

    if update_fields:
        safe_save_profile(profile, update_fields)

    return profile


class PoinrouteAccountAdapter(DefaultAccountAdapter):
    """
    일반 로그인/가입 후 이동 제어.

    구글/네이버/카카오 로그인 후에도 닉네임이 없으면
    posts:list로 보내서 닉네임 모달이 뜨게 한다.
    """

    def get_login_redirect_url(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            sync_profile_email_without_nickname(user)

            if user_needs_nickname(user):
                return get_nickname_required_url()

        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            sync_profile_email_without_nickname(user)

            if user_needs_nickname(user):
                return get_nickname_required_url()

        return super().get_signup_redirect_url(request)


class PoinrouteSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    구글/네이버/카카오 소셜 로그인 담당.

    핵심:
    - 카카오는 이메일 권한이 없어도 로그인 가능하게 한다.
    - username만 자동 생성한다.
    - Profile.nickname은 절대 자동 생성하지 않는다.
    - 기존 Profile.nickname도 절대 지우지 않는다.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        provider = sociallogin.account.provider
        uid = sociallogin.account.uid

        email = extract_social_email(sociallogin, data)
        name = extract_social_name(sociallogin, data)

        if email:
            user.email = email

        if not user.username:
            user.username = make_unique_username(
                email=email,
                name=name,
                provider=provider,
                uid=uid,
            )

        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        email = extract_social_email(sociallogin, {})
        if email and not user.email:
            user.email = email
            user.save(update_fields=["email"])

        profile = get_or_create_profile(user)
        field_names = get_profile_field_names()

        update_fields = []

        if (
            "recovery_email" in field_names
            and user.email
            and not getattr(profile, "recovery_email", "")
        ):
            profile.recovery_email = user.email
            update_fields.append("recovery_email")

        # 중요:
        # 닉네임은 자동 생성하지 않는다.
        # 단, DB에서 None이면 빈 문자열로만 정리한다.
        # 기존 사용자가 직접 정한 닉네임은 절대 지우지 않는다.
        if "nickname" in field_names and getattr(profile, "nickname", None) is None:
            profile.nickname = ""
            update_fields.append("nickname")

        if "points" in field_names and getattr(profile, "points", None) is None:
            profile.points = 0
            update_fields.append("points")

        if (
            "total_earned_points" in field_names
            and getattr(profile, "total_earned_points", None) is None
        ):
            profile.total_earned_points = 0
            update_fields.append("total_earned_points")

        if update_fields:
            safe_save_profile(profile, update_fields)

        return user

    def get_login_redirect_url(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            sync_profile_email_without_nickname(user)

            if user_needs_nickname(user):
                return get_nickname_required_url()

        return super().get_login_redirect_url(request)
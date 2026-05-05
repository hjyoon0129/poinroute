from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, NicknameForm, SignupForm
from .models import Profile


User = get_user_model()

DEFAULT_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _resolve_default_url(default="posts:list"):
    if not default:
        return "/"

    if isinstance(default, str) and default.startswith("/"):
        return default

    try:
        return reverse(default)
    except NoReverseMatch:
        return "/"


def _safe_next_url(request, default="posts:list"):
    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return _resolve_default_url(default)


def _safe_post_or_referer_url(request, default="posts:list"):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return _resolve_default_url(default)


def _add_query_param(url, key, value):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[key] = value

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _normalize_profile_after_auth(user):
    """
    일반/소셜 로그인 직후 프로필 정리.

    - 닉네임은 자동 생성하지 않는다.
    - nickname=""이면 None으로 정리한다.
    - user.email이 있으면 recovery_email에 보조 저장한다.
    """
    profile = _get_profile(user)
    update_fields = []

    if getattr(profile, "nickname", None) == "":
        profile.nickname = None
        update_fields.append("nickname")

    if getattr(user, "email", "") and not getattr(profile, "recovery_email", ""):
        profile.recovery_email = user.email
        update_fields.append("recovery_email")

    if update_fields:
        update_fields.append("updated_at")
        profile.save(update_fields=list(dict.fromkeys(update_fields)))

    return profile


def _needs_nickname(user):
    if not user or not user.is_authenticated:
        return False

    profile = _get_profile(user)
    return not bool((profile.nickname or "").strip())


def _nickname_required_redirect_url():
    """
    닉네임이 없는 유저는 base.html을 상속하는 루트 목록으로 보낸다.
    그래야 닉네임/보호 이메일 모달이 뜬다.
    """
    url = _resolve_default_url("posts:list")
    return _add_query_param(url, "nickname", "1")


def _redirect_after_auth(request, user, default="posts:list"):
    profile = _normalize_profile_after_auth(user)

    if not (profile.nickname or "").strip():
        return redirect(_nickname_required_redirect_url())

    return redirect(_safe_next_url(request, default=default))


def _get_user_by_login_id(login_id):
    login_id = (login_id or "").strip()

    if not login_id:
        return None

    user = User.objects.filter(username__iexact=login_id).first()

    if user:
        return user

    user = User.objects.filter(email__iexact=login_id).first()

    if user:
        return user

    profile = Profile.objects.select_related("user").filter(
        recovery_email__iexact=login_id
    ).first()

    if profile:
        return profile.user

    return None


def _is_social_provider_ready(provider):
    try:
        from allauth.socialaccount.models import SocialApp
    except Exception:
        return False

    try:
        site_id = getattr(settings, "SITE_ID", 1)

        return SocialApp.objects.filter(
            provider=provider,
            sites__id=site_id,
        ).exists()
    except Exception:
        return False


def _social_ready_context():
    return {
        "google": _is_social_provider_ready("google"),
        "kakao": _is_social_provider_ready("kakao"),
        "naver": _is_social_provider_ready("naver"),
    }


def _is_valid_email(email):
    email = (email or "").strip()

    if not email:
        return False

    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def signup_view(request):
    if request.user.is_authenticated:
        if _needs_nickname(request.user):
            return redirect(_nickname_required_redirect_url())

        return redirect("posts:list")

    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            user = form.save()

            profile = _get_profile(user)

            # 일반 신규 가입자도 가입 직후 닉네임은 비워둔다.
            # 빈 문자열 대신 None으로 저장해서 unique 충돌을 막는다.
            profile.nickname = None

            update_fields = ["nickname", "updated_at"]

            if user.email and not profile.recovery_email:
                profile.recovery_email = user.email
                update_fields.append("recovery_email")

            profile.save(update_fields=list(dict.fromkeys(update_fields)))

            # 중요:
            # settings.py에 인증 backend가 2개 있으므로 backend를 명시해야 한다.
            login(
                request,
                user,
                backend=DEFAULT_AUTH_BACKEND,
            )

            messages.success(
                request,
                "회원가입이 완료되었습니다. 닉네임과 보호 이메일을 설정해주세요.",
            )

            return redirect(_nickname_required_redirect_url())
    else:
        form = SignupForm()

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
            "social_ready": _social_ready_context(),
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        if _needs_nickname(request.user):
            return redirect(_nickname_required_redirect_url())

        return redirect("posts:list")

    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            login_id = form.cleaned_data["login_id"].strip()
            pin = form.cleaned_data["pin"]

            user_obj = _get_user_by_login_id(login_id)

            if not user_obj:
                form.add_error(None, "아이디 또는 보호 이메일을 찾을 수 없습니다.")
            else:
                user = authenticate(
                    request,
                    username=user_obj.get_username(),
                    password=pin,
                )

                if user is None:
                    form.add_error(None, "핀번호가 올바르지 않습니다.")
                else:
                    # authenticate()로 온 user는 backend가 붙지만,
                    # 명시해도 문제 없어서 안정적으로 지정한다.
                    login(
                        request,
                        user,
                        backend=DEFAULT_AUTH_BACKEND,
                    )

                    profile = _normalize_profile_after_auth(user)

                    if not (profile.nickname or "").strip():
                        messages.info(
                            request,
                            "닉네임과 보호 이메일을 먼저 설정해주세요.",
                        )
                        return redirect(_nickname_required_redirect_url())

                    return redirect(_safe_next_url(request, default="posts:list"))
    else:
        form = LoginForm()

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "social_ready": _social_ready_context(),
        },
    )


def logout_view(request):
    logout(request)
    messages.success(request, "로그아웃되었습니다.")
    return redirect("posts:list")


@require_POST
@login_required
def set_nickname(request):
    profile = _get_profile(request.user)

    next_url = _safe_post_or_referer_url(request, default="posts:list")
    recovery_email = (request.POST.get("recovery_email") or "").strip().lower()

    if not _is_valid_email(recovery_email):
        messages.error(request, "보호 이메일을 올바르게 입력해주세요.")
        return redirect(_nickname_required_redirect_url())

    form = NicknameForm(request.POST, user=request.user)

    if form.is_valid():
        profile.nickname = form.cleaned_data["nickname"]
        profile.recovery_email = recovery_email

        profile.save(
            update_fields=[
                "nickname",
                "recovery_email",
                "updated_at",
            ]
        )

        # 카카오처럼 user.email이 비어 있는 계정은 보호 이메일을 보조 저장한다.
        # 이미 다른 유저가 같은 이메일을 쓰면 User.email에는 넣지 않고 Profile.recovery_email만 쓴다.
        if not request.user.email:
            email_exists = (
                User.objects
                .filter(email__iexact=recovery_email)
                .exclude(pk=request.user.pk)
                .exists()
            )

            if not email_exists:
                request.user.email = recovery_email
                request.user.save(update_fields=["email"])

        messages.success(request, f"{profile.nickname} 닉네임이 설정되었습니다.")
        return redirect(next_url)

    for field_errors in form.errors.values():
        for error in field_errors:
            messages.error(request, error)

    return redirect(_nickname_required_redirect_url())
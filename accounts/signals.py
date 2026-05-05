from allauth.account.signals import user_logged_in, user_signed_up
from django.dispatch import receiver

from .models import Profile


def _ensure_profile_for_user(user, *, clear_nickname_for_new_social=False):
    profile, _ = Profile.objects.get_or_create(user=user)

    update_fields = []

    if user.email and not profile.recovery_email:
        profile.recovery_email = user.email
        update_fields.append("recovery_email")

    """
    핵심:
    새 구글 가입자는 닉네임을 자동으로 구글 이름/이메일 앞부분으로 넣지 않는다.
    반드시 빈 값으로 둬야 base.html의 닉네임 모달 조건에 걸린다.
    """
    if clear_nickname_for_new_social:
        profile.nickname = ""
        update_fields.append("nickname")

    if update_fields:
        update_fields.append("updated_at")
        profile.save(update_fields=update_fields)

    return profile


@receiver(user_signed_up)
def handle_user_signed_up(request, user, **kwargs):
    """
    일반 가입/소셜 가입 공통.
    새 가입자는 닉네임을 비워둔다.
    """
    _ensure_profile_for_user(
        user,
        clear_nickname_for_new_social=True,
    )


@receiver(user_logged_in)
def handle_user_logged_in(request, user, **kwargs):
    """
    기존 구글 로그인 유저도 프로필이 없으면 생성한다.
    단, 기존 닉네임이 있으면 절대 지우지 않는다.
    """
    _ensure_profile_for_user(
        user,
        clear_nickname_for_new_social=False,
    )
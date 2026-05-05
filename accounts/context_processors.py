from allauth.socialaccount.models import SocialApp


def social_login_ready(request):
    ready = {
        "google": False,
        "kakao": False,
        "naver": False,
    }

    try:
        apps = SocialApp.objects.values_list("provider", flat=True)
        provider_set = set(apps)

        ready["google"] = "google" in provider_set
        ready["kakao"] = "kakao" in provider_set
        ready["naver"] = "naver" in provider_set

    except Exception:
        pass

    return {
        "social_ready": ready,
    }
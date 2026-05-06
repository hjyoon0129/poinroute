from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView

from config.sitemaps import StaticViewSitemap
from config.views import robots_txt


sitemaps = {
    "static": StaticViewSitemap,
}


urlpatterns = [
    # =========================
    # SEO
    # =========================
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),

    # =========================
    # Legacy auth redirects
    # 예전 코드에서 /auth/login/으로 보내는 경우 404 방지
    # /auth/login/?next=/points/ -> /accounts/login/?next=/points/
    # =========================
    path(
        "auth/login/",
        RedirectView.as_view(
            url="/accounts/login/",
            permanent=False,
            query_string=True,
        ),
        name="legacy_login_redirect",
    ),
    path(
        "auth/signup/",
        RedirectView.as_view(
            url="/accounts/signup/",
            permanent=False,
            query_string=True,
        ),
        name="legacy_signup_redirect",
    ),
    path(
        "auth/logout/",
        RedirectView.as_view(
            url="/accounts/logout/",
            permanent=False,
            query_string=True,
        ),
        name="legacy_logout_redirect",
    ),

    # =========================
    # Admin
    # =========================
    path(settings.ADMIN_URL, admin.site.urls),

    # =========================
    # Accounts
    # 커스텀 로그인/회원가입
    # /accounts/login/
    # /accounts/signup/
    # =========================
    path("accounts/", include("accounts.urls")),

    # django-allauth 소셜 로그인
    # /accounts/google/login/
    # /accounts/kakao/login/
    # /accounts/naver/login/
    # /accounts/password/reset/
    # =========================
    path("accounts/", include("allauth.urls")),

    # =========================
    # Service apps
    # =========================
    path("community/", include("community.urls")),
    path("auctions/", include("auctions.urls")),
    path("points/", include("points.urls")),
    path("support/", include("support.urls")),

    # 메인 posts 앱은 마지막에 두는 게 안전함
    path("", include("posts.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
"""
Django settings for config project.
Poinroute production-ready style settings.

- .env 기반 설정
- PostgreSQL / DATABASE_URL 사용
- sqlite 미사용
- django-allauth 기반 Google / Naver / Kakao 소셜 로그인 준비
- 자체 로그인은 accounts 앱에서 아이디 + 6자리 PIN 방식으로 처리
- 일반 / Google / Naver / Kakao 로그인 후 닉네임이 없으면 닉네임 모달 표시
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


# =========================
# Base paths
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# =========================
# Helpers
# =========================
def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def env_list(name, default=""):
    return [
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    ]


# =========================
# Core
# =========================
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set in .env")

DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,poinroute.com,www.poinroute.com",
)


# =========================
# Application definition
# =========================
INSTALLED_APPS = [
    # Django 기본 앱
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    'django.contrib.sitemaps',

    # django-allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Social providers
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.naver",
    "allauth.socialaccount.providers.kakao",

    # Poinroute 프로젝트 앱
    "accounts.apps.AccountsConfig",
    "core",
    "users",
    "posts",
    "places",
    "interactions",
    "moderation",
    "points",
    "billing",
    "auctions",
    "trades",
    "community",
    "support",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # 소셜 로그인 버튼 활성/비활성 표시
                "accounts.context_processors.social_login_ready",

                # 여행 루트 검수 결과 모달
                "posts.context_processors.review_notice",

                # 포인트샵 쿠폰/광고포인트 결과 모달
                "points.context_processors.point_notices",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# =========================
# Database
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env. PostgreSQL DATABASE_URL is required.")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}


# =========================
# Password validation
# =========================
# Poinroute는 자체 일반 로그인에서 6자리 PIN을 사용하므로
# Django 기본 비밀번호 검사는 비활성화한다.
AUTH_PASSWORD_VALIDATORS = []


# =========================
# Internationalization
# =========================
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"

USE_I18N = True
USE_TZ = True


# =========================
# Static files / Media
# =========================
STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =========================
# Default primary key
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================
# Sites framework
# =========================
SITE_ID = int(os.getenv("SITE_ID", "1"))


# =========================
# Login / Logout
# =========================
LOGIN_URL = "/auth/login/"

# 닉네임 모달은 base.html을 상속하는 posts:list에서 뜨게 한다.
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"


# =========================
# Authentication backends
# =========================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]


# =========================
# django-allauth
# =========================
# 자체 일반 로그인/회원가입은 accounts 앱에서 처리.
# allauth는 Google / Naver / Kakao 소셜 로그인 연결용으로 사용.

ACCOUNT_ADAPTER = "accounts.adapters.PoinrouteAccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.PoinrouteSocialAccountAdapter"

ACCOUNT_EMAIL_SUBJECT_PREFIX = ""

# 중요:
# 카카오는 이메일 권한이 없을 수 있으므로 allauth 로그인 기준을 email로 잡으면 안 된다.
# 일반 로그인에서 보호 이메일/PIN 처리는 accounts 앱 view에서 직접 처리한다.
ACCOUNT_LOGIN_METHODS = {"username"}

# 최신 allauth 방식.
# username은 allauth 시스템 체크 통과용이며,
# 실제 일반 가입/로그인은 accounts 앱 화면에서 처리한다.
ACCOUNT_SIGNUP_FIELDS = [
    "username*",
    "email",
    "password1*",
    "password2*",
]

# email을 로그인 방식으로 쓰지 않으므로 False 가능.
# 카카오 이메일 없는 가입을 막지 않기 위해 email 필수/유니크를 강제하지 않는다.
ACCOUNT_UNIQUE_EMAIL = False
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False

ACCOUNT_SESSION_REMEMBER = None

# 소셜 로그인 자동 처리
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True

# 개발 중 소셜 로그인 실패 원인을 노란 에러페이지/터미널에 보여준다.
# 운영 DEBUG=False에서는 False가 된다.
SOCIALACCOUNT_RAISE_EXCEPTIONS = DEBUG

# Google/Naver처럼 이메일이 있는 provider는 기존 계정 연결 가능.
# Kakao는 이메일이 없으면 provider uid 기반으로 새 계정 생성.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_STORE_TOKENS = False

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "prompt": "select_account",
            "access_type": "online",
        },
        "EMAIL_AUTHENTICATION": True,
        "VERIFIED_EMAIL": True,
    },
    "naver": {
        "SCOPE": [
            "profile",
            "email",
        ],
    },
    "kakao": {
        # 카카오 이메일 권한이 없으므로 account_email 넣으면 안 됨.
        "SCOPE": [
            "profile_nickname",
            "profile_image",
        ],
    },
}


# =========================
# Session / Cookie
# =========================
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"


# =========================
# CSRF / Security
# =========================
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,https://poinroute.com,https://www.poinroute.com",
)

if DEBUG:
    SECURE_PROXY_SSL_HEADER = None
else:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool(
    "SECURE_SSL_REDIRECT",
    False if DEBUG else True,
)

SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    False if DEBUG else True,
)

CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    False if DEBUG else True,
)

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

SECURE_HSTS_SECONDS = int(
    os.getenv(
        "SECURE_HSTS_SECONDS",
        "0" if DEBUG else "31536000",
    )
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False if DEBUG else True,
)

SECURE_HSTS_PRELOAD = env_bool(
    "SECURE_HSTS_PRELOAD",
    False if DEBUG else True,
)


# =========================
# Admin URL
# =========================
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")


# =========================
# Email
# =========================
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "Poinroute <noreply@poinroute.com>",
)

SERVER_EMAIL = os.getenv(
    "SERVER_EMAIL",
    DEFAULT_FROM_EMAIL,
)

PASSWORD_RESET_TIMEOUT = int(
    os.getenv(
        "PASSWORD_RESET_TIMEOUT",
        str(60 * 60),
    )
)


# =========================
# Cache
# =========================
USE_REDIS = env_bool("USE_REDIS", False)

if USE_REDIS:
    REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1")

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# =========================
# Logging
# =========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
}
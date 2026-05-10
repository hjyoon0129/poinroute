from __future__ import annotations

import ipaddress
import time
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils import timezone


BOT_UA_KEYWORDS = [
    "bot",
    "crawl",
    "spider",
    "slurp",
    "facebookexternalhit",
    "meta-externalagent",
    "gptbot",
    "googlebot",
    "bingbot",
    "naverbot",
    "yeti",
    "daum",
    "curl",
    "wget",
    "python-requests",
    "scrapy",
    "ahrefs",
    "semrush",
    "mj12bot",
    "bytespider",
]

BAD_AUTH_BOT_UA_KEYWORDS = [
    "meta-externalagent",
    "gptbot",
    "bytespider",
    "ahrefsbot",
    "semrushbot",
    "mj12bot",
    "python-requests",
    "curl",
    "wget",
    "scrapy",
]

SENSITIVE_PATH_PREFIXES = [
    "/accounts/",
    "/admin/",
    "/hjyoon0129/",
]

AUTH_LOG_PATH_PREFIXES = [
    "/accounts/login/",
    "/accounts/signup/",
    "/accounts/logout/",
    "/accounts/google/login/",
    "/accounts/kakao/login/",
    "/accounts/naver/login/",
    "/password",
]

STATIC_SKIP_PREFIXES = [
    "/static/",
    "/media/",
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
]


class PoinrouteSecurityMiddleware:
    """
    포인루트 방문/봇/이상유입 기록 및 Django 레벨 2차 차단 미들웨어.

    역할:
    1. 정상 방문자 / 봇 / 의심 요청 분류
    2. VisitorLog / PageViewLog / RequestLog 저장
    3. LoginAttemptLog 저장
    4. BlockedIP / IPBlockRule 기반 차단
    5. accounts next 루프 URL 차단
    6. meta-externalagent, GPTBot 등이 로그인/회원가입 민감 경로 접근 시 차단

    주의:
    nginx 차단이 1차 방어선이고, 이 미들웨어는 2차 방어선이다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started_at = time.monotonic()

        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "") or ""
        referer = request.META.get("HTTP_REFERER", "") or ""
        path = request.path or ""
        full_path = request.get_full_path() or path

        if self.should_skip_request(path):
            return self.get_response(request)

        is_bot = self.looks_like_bot(user_agent)
        is_sensitive = self.is_sensitive_path(path)
        is_bad_loop = self.is_bad_next_loop(path, full_path)
        is_suspicious = is_bad_loop or self.is_suspicious_path(full_path)
        is_blocked = False
        block_reason = ""

        if self.is_ip_blocked(ip_address):
            is_blocked = True
            block_reason = "blocked_ip_rule"

        elif is_bad_loop:
            is_blocked = True
            block_reason = "bad_next_loop"

        elif is_sensitive and self.is_bad_auth_bot(user_agent):
            is_blocked = True
            block_reason = "bad_bot_on_sensitive_path"

        if is_blocked:
            response = HttpResponseForbidden("Forbidden")
            response_ms = self.elapsed_ms(started_at)

            self.safe_log_all(
                request=request,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                path=path,
                full_path=full_path,
                status_code=403,
                response_ms=response_ms,
                is_bot=is_bot,
                is_suspicious=True,
                is_blocked=True,
                block_reason=block_reason,
            )
            return response

        try:
            response = self.get_response(request)
        except PermissionDenied:
            response_ms = self.elapsed_ms(started_at)
            self.safe_log_all(
                request=request,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                path=path,
                full_path=full_path,
                status_code=403,
                response_ms=response_ms,
                is_bot=is_bot,
                is_suspicious=True,
                is_blocked=True,
                block_reason="permission_denied",
            )
            raise

        response_ms = self.elapsed_ms(started_at)
        status_code = getattr(response, "status_code", None)

        self.safe_log_all(
            request=request,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            path=path,
            full_path=full_path,
            status_code=status_code,
            response_ms=response_ms,
            is_bot=is_bot,
            is_suspicious=is_suspicious,
            is_blocked=False,
            block_reason="",
        )

        return response

    # ============================================================
    # request 판단
    # ============================================================

    def get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = request.META.get("HTTP_X_REAL_IP", "")
        if x_real_ip:
            return x_real_ip.strip()

        return request.META.get("REMOTE_ADDR", "") or "0.0.0.0"

    def should_skip_request(self, path: str) -> bool:
        if getattr(settings, "POINROUTE_SECURITY_LOG_STATIC", False):
            return False

        lower = (path or "").lower()
        return any(lower.startswith(prefix) for prefix in STATIC_SKIP_PREFIXES)

    def looks_like_bot(self, user_agent: str) -> bool:
        ua = (user_agent or "").lower()
        return any(keyword in ua for keyword in BOT_UA_KEYWORDS)

    def is_bad_auth_bot(self, user_agent: str) -> bool:
        ua = (user_agent or "").lower()
        return any(keyword in ua for keyword in BAD_AUTH_BOT_UA_KEYWORDS)

    def is_sensitive_path(self, path: str) -> bool:
        lower = (path or "").lower()
        return any(lower.startswith(prefix) for prefix in SENSITIVE_PATH_PREFIXES)

    def is_auth_log_path(self, path: str) -> bool:
        lower = (path or "").lower()
        return any(lower.startswith(prefix) for prefix in AUTH_LOG_PATH_PREFIXES)

    def is_google_callback(self, path: str) -> bool:
        lower = (path or "").lower()
        return lower.startswith("/accounts/google/login/callback/")

    def is_bad_next_loop(self, path: str, full_path: str) -> bool:
        """
        /accounts/login/?next=/accounts/signup/?next=/accounts/login/...
        같은 비정상 루프 차단.

        정상 Google callback은 절대 차단하지 않는다.
        """
        if self.is_google_callback(path):
            return False

        p = (path or "").lower()
        fp = (full_path or "").lower()

        if not (
            p.startswith("/accounts/login/")
            or p.startswith("/accounts/signup/")
            or p.startswith("/accounts/google/login/")
        ):
            return False

        next_count = (
            fp.count("next=")
            + fp.count("%3fnext")
            + fp.count("%253fnext")
            + fp.count("%25253fnext")
            + fp.count("%2525253fnext")
        )

        accounts_count = (
            fp.count("/accounts/login")
            + fp.count("/accounts/signup")
            + fp.count("/accounts/google/login")
            + fp.count("%2faccounts%2flogin")
            + fp.count("%2faccounts%2fsignup")
            + fp.count("%2faccounts%2fgoogle%2flogin")
            + fp.count("%252faccounts%252flogin")
            + fp.count("%252faccounts%252fsignup")
            + fp.count("%252faccounts%252fgoogle%252flogin")
        )

        if next_count >= 2:
            return True

        if accounts_count >= 2 and "next" in fp:
            return True

        if len(fp) >= 600 and "next" in fp and "/accounts/" in fp:
            return True

        if "%252525" in fp and "accounts" in fp:
            return True

        return False

    def is_suspicious_path(self, full_path: str) -> bool:
        fp = (full_path or "").lower()

        suspicious_keywords = [
            "/wp-admin",
            "/xmlrpc.php",
            "/.env",
            "/.git",
            "/phpmyadmin",
            "/adminer",
            "/server-status",
            "select%20",
            "union%20",
            "../",
            "%2e%2e",
            "%00",
        ]

        return any(keyword in fp for keyword in suspicious_keywords)

    def classify_visitor(
        self,
        *,
        is_bot: bool,
        is_suspicious: bool,
        is_blocked: bool,
    ) -> str:
        if is_blocked:
            return "Blocked"
        if is_suspicious:
            return "Suspicious"
        if is_bot:
            return "Bot"
        return "Maybe Human"

    def elapsed_ms(self, started_at: float) -> int:
        return int((time.monotonic() - started_at) * 1000)

    # ============================================================
    # DB 차단 규칙
    # ============================================================

    def is_ip_blocked(self, ip_address: str) -> bool:
        if not ip_address:
            return False

        try:
            from .models import BlockedIP, IPBlockRule

            if BlockedIP.objects.filter(ip_address=ip_address, is_active=True).exists():
                return True

            try:
                current_ip = ipaddress.ip_address(ip_address)
            except ValueError:
                return False

            cidrs = IPBlockRule.objects.filter(is_active=True).values_list("cidr", flat=True)

            for cidr in cidrs:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                except ValueError:
                    continue

                if current_ip in network:
                    return True

        except (OperationalError, ProgrammingError, DatabaseError):
            return False
        except Exception:
            return False

        return False

    # ============================================================
    # 로그 저장
    # ============================================================

    def safe_log_all(
        self,
        *,
        request: HttpRequest,
        ip_address: str,
        user_agent: str,
        referer: str,
        path: str,
        full_path: str,
        status_code: int | None,
        response_ms: int,
        is_bot: bool,
        is_suspicious: bool,
        is_blocked: bool,
        block_reason: str,
    ) -> None:
        try:
            self.log_all(
                request=request,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                path=path,
                full_path=full_path,
                status_code=status_code,
                response_ms=response_ms,
                is_bot=is_bot,
                is_suspicious=is_suspicious,
                is_blocked=is_blocked,
                block_reason=block_reason,
            )
        except (OperationalError, ProgrammingError, DatabaseError):
            return
        except Exception:
            return

    def log_all(
        self,
        *,
        request: HttpRequest,
        ip_address: str,
        user_agent: str,
        referer: str,
        path: str,
        full_path: str,
        status_code: int | None,
        response_ms: int,
        is_bot: bool,
        is_suspicious: bool,
        is_blocked: bool,
        block_reason: str,
    ) -> None:
        from .models import LoginAttemptLog, PageViewLog, RequestLog, SecurityEvent, VisitorLog

        visitor_type = self.classify_visitor(
            is_bot=is_bot,
            is_suspicious=is_suspicious,
            is_blocked=is_blocked,
        )

        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None

        method = request.method or "GET"
        query_string = request.META.get("QUERY_STRING", "") or ""

        should_log_all_requests = getattr(settings, "POINROUTE_SECURITY_LOG_ALL_REQUESTS", True)
        should_log_pageviews = getattr(settings, "POINROUTE_SECURITY_LOG_PAGEVIEWS", True)

        # 1) 일자별 방문자 집계
        visitor, created = VisitorLog.objects.get_or_create(
            visit_date=timezone.localdate(),
            ip_address=ip_address,
            defaults={
                "country": "Unknown",
                "type": visitor_type,
                "path": full_path[:2000],
                "method": method[:12],
                "user_agent": user_agent[:2000],
                "referer": referer[:2000],
                "user": user,
                "request_count": 1,
                "is_bot": is_bot,
                "is_blocked": is_blocked,
            },
        )

        if not created:
            visitor.request_count = models.F("request_count") + 1
            visitor.type = self.pick_stronger_type(visitor.type, visitor_type)
            visitor.path = full_path[:2000]
            visitor.method = method[:12]
            visitor.user_agent = user_agent[:2000]
            visitor.referer = referer[:2000]
            visitor.is_bot = visitor.is_bot or is_bot
            visitor.is_blocked = visitor.is_blocked or is_blocked
            if user and not visitor.user_id:
                visitor.user = user
            visitor.save(
                update_fields=[
                    "request_count",
                    "type",
                    "path",
                    "method",
                    "user_agent",
                    "referer",
                    "is_bot",
                    "is_blocked",
                    "user",
                    "last_seen_at",
                ]
            )

        # 2) 상세 요청 로그
        must_log = (
            should_log_all_requests
            or is_blocked
            or is_suspicious
            or is_bot
            or self.is_auth_log_path(path)
            or (status_code is not None and status_code >= 400)
        )

        if must_log:
            RequestLog.objects.create(
                ip_address=ip_address,
                method=method[:12],
                path=path[:2000],
                full_path=full_path[:4000],
                referer=referer[:2000],
                user_agent=user_agent[:2000],
                status_code=status_code,
                type=visitor_type,
                is_bot=is_bot,
                is_suspicious=is_suspicious,
                is_blocked=is_blocked,
                response_ms=response_ms,
                user=user,
            )

        # 3) 페이지뷰 로그
        if should_log_pageviews:
            PageViewLog.objects.create(
                ip_address=ip_address,
                country="Unknown",
                method=method[:12],
                path=path[:2000],
                query_string=query_string[:2000],
                referer=referer[:2000],
                user_agent=user_agent[:2000],
                status_code=status_code,
                type=visitor_type,
                is_bot=is_bot,
                is_suspicious=is_suspicious,
                is_blocked=is_blocked,
                response_ms=response_ms,
                user=user,
            )

        # 4) 로그인/회원가입 관련 시도 로그
        if self.is_auth_log_path(path):
            identifier_data = self.extract_login_identifier(request)

            LoginAttemptLog.objects.create(
                ip_address=ip_address,
                path=full_path[:3000],
                method=method[:12],
                username=identifier_data.get("username", "")[:255],
                email=identifier_data.get("email", "")[:255],
                identifier=identifier_data.get("identifier", "")[:255],
                success=self.guess_login_success(path, method, status_code),
                status_code=status_code,
                user_agent=user_agent[:2000],
                referer=referer[:2000],
                reason=block_reason[:255],
                user=user,
            )

        # 5) 보안 이벤트
        if is_blocked or is_suspicious or (status_code is not None and status_code >= 500):
            if is_blocked:
                severity = "DANGER"
                event_type = "BLOCKED_REQUEST"
                message = block_reason or "blocked request"
            elif status_code is not None and status_code >= 500:
                severity = "CRITICAL"
                event_type = "SERVER_ERROR"
                message = "server error response"
            else:
                severity = "WARNING"
                event_type = "SUSPICIOUS_REQUEST"
                message = "suspicious request"

            SecurityEvent.objects.create(
                event_type=event_type,
                severity=severity,
                ip_address=ip_address,
                method=method[:12],
                path=full_path[:4000],
                status_code=status_code,
                user_agent=user_agent[:2000],
                referer=referer[:2000],
                message=message,
                user=user,
            )

    def pick_stronger_type(self, old_type: str, new_type: str) -> str:
        priority = {
            "Maybe Human": 1,
            "Human": 2,
            "Bot": 3,
            "Suspicious": 4,
            "Blocked": 5,
        }

        old_score = priority.get(old_type, 0)
        new_score = priority.get(new_type, 0)

        return new_type if new_score > old_score else old_type

    def extract_login_identifier(self, request: HttpRequest) -> dict[str, str]:
        if request.method.upper() != "POST":
            return {"username": "", "email": "", "identifier": ""}

        try:
            post = request.POST
        except Exception:
            return {"username": "", "email": "", "identifier": ""}

        username = (
            post.get("username")
            or post.get("login")
            or post.get("account")
            or ""
        )

        email = (
            post.get("email")
            or post.get("recovery_email")
            or ""
        )

        identifier = (
            post.get("identifier")
            or post.get("login")
            or username
            or email
            or ""
        )

        # 비밀번호, PIN, 인증코드 등은 절대 저장하지 않는다.
        return {
            "username": str(username),
            "email": str(email),
            "identifier": str(identifier),
        }

    def guess_login_success(self, path: str, method: str, status_code: int | None) -> bool | None:
        lower_path = (path or "").lower()

        if not self.is_auth_log_path(lower_path):
            return None

        if method.upper() != "POST":
            return None

        if status_code in [301, 302, 303]:
            return True

        if status_code in [400, 401, 403, 429]:
            return False

        return None
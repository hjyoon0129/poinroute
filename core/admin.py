from __future__ import annotations

from typing import Any, Iterable

from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin.sites import AlreadyRegistered
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator


admin.site.site_header = "Poinroute Admin"
admin.site.site_title = "Poinroute Admin"
admin.site.index_title = "포인루트 관리자"


# ============================================================
# 공통 유틸
# ============================================================

APP_LABEL = "core"


def get_model_if_exists(model_name: str):
    try:
        return apps.get_model(APP_LABEL, model_name)
    except LookupError:
        return None


def field_names(model: type[models.Model]) -> set[str]:
    return {field.name for field in model._meta.get_fields() if hasattr(field, "name")}


def first_existing_field(model: type[models.Model], candidates: Iterable[str]) -> str | None:
    names = field_names(model)
    for name in candidates:
        if name in names:
            return name
    return None


def get_obj_value(obj: Any, candidates: Iterable[str], default: Any = "-") -> Any:
    for name in candidates:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None and value != "":
                return value
    return default


def short_text(value: Any, length: int = 80) -> str:
    if value is None:
        return "-"
    return Truncator(str(value)).chars(length)


def status_color(status: int | str | None) -> str:
    try:
        code = int(status)
    except Exception:
        return "#64748b"

    if 200 <= code < 300:
        return "#22c55e"
    if 300 <= code < 400:
        return "#38bdf8"
    if code == 403:
        return "#f59e0b"
    if code == 404:
        return "#94a3b8"
    if code >= 500:
        return "#ef4444"
    return "#64748b"


def looks_like_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    keywords = [
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
        "daum",
        "yeti",
        "curl",
        "wget",
        "python-requests",
        "scrapy",
        "ahrefs",
        "semrush",
        "mj12bot",
        "bytespider",
    ]
    return any(word in ua for word in keywords)


def is_suspicious_path(path: str) -> bool:
    p = (path or "").lower()
    suspicious_keywords = [
        "/accounts/login",
        "/accounts/signup",
        "/accounts/google/login",
        "/password",
        "/admin",
        "/wp-admin",
        "/xmlrpc.php",
        "/.env",
        "/phpmyadmin",
        "/.git",
        "next=",
        "%253fnext",
        "%25253fnext",
    ]
    return any(word in p for word in suspicious_keywords)


# ============================================================
# 트래픽/방문 로그 공통 Admin
# ============================================================

class TrafficLogAdmin(admin.ModelAdmin):
    list_per_page = 50
    date_hierarchy = None
    actions = [
        "mark_as_human",
        "mark_as_bot",
        "mark_as_suspicious",
        "mark_as_blocked",
    ]

    def get_list_display(self, request):
        return (
            "created_display",
            "ip_display",
            "path_display",
            "status_display",
            "type_display",
            "country_display",
            "user_display",
            "ua_display",
        )

    def get_search_fields(self, request):
        model = self.model
        candidates = [
            "ip_address",
            "ip",
            "remote_addr",
            "path",
            "url",
            "request_path",
            "user_agent",
            "ua",
            "country",
            "type",
            "visitor_type",
            "kind",
            "method",
        ]
        return tuple(name for name in candidates if name in field_names(model))

    def get_list_filter(self, request):
        model = self.model
        candidates = [
            "type",
            "visitor_type",
            "kind",
            "method",
            "status_code",
            "status",
            "country",
            "is_bot",
            "is_blocked",
            "blocked",
            "created_at",
            "visit_date",
        ]
        return tuple(name for name in candidates if name in field_names(model))

    def get_readonly_fields(self, request, obj=None):
        names = field_names(self.model)
        readonly = [
            "ip_address",
            "ip",
            "remote_addr",
            "path",
            "url",
            "request_path",
            "method",
            "status_code",
            "status",
            "user_agent",
            "ua",
            "referer",
            "referrer",
            "country",
            "created_at",
            "updated_at",
            "visit_date",
        ]
        return tuple(name for name in readonly if name in names)

    def get_ordering(self, request):
        model = self.model
        for name in ["-created_at", "-visit_date", "-id"]:
            field = name.lstrip("-")
            if field in field_names(model):
                return (name,)
        return ("-pk",)

    @admin.display(description="시간")
    def created_display(self, obj):
        value = get_obj_value(obj, ["created_at", "visit_date", "timestamp", "datetime"], None)
        if not value:
            return "-"
        try:
            return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    @admin.display(description="IP")
    def ip_display(self, obj):
        ip = get_obj_value(obj, ["ip_address", "ip", "remote_addr"], "-")
        return format_html("<strong>{}</strong>", ip)

    @admin.display(description="PATH / URL")
    def path_display(self, obj):
        path = get_obj_value(obj, ["path", "url", "request_path", "full_path"], "-")
        text = short_text(path, 120)

        if is_suspicious_path(str(path)):
            return format_html(
                '<span style="color:#ef4444;font-weight:700;">{}</span>',
                text,
            )

        return text

    @admin.display(description="STATUS")
    def status_display(self, obj):
        status = get_obj_value(obj, ["status_code", "status", "response_status"], "-")
        color = status_color(status)
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            'background:{}22;color:{};font-weight:700;">{}</span>',
            color,
            color,
            status,
        )

    @admin.display(description="TYPE")
    def type_display(self, obj):
        value = get_obj_value(obj, ["type", "visitor_type", "kind", "classification"], None)
        ua = str(get_obj_value(obj, ["user_agent", "ua"], ""))
        path = str(get_obj_value(obj, ["path", "url", "request_path"], ""))

        if not value or value == "-":
            if looks_like_bot(ua):
                value = "Bot"
            elif is_suspicious_path(path):
                value = "Suspicious"
            else:
                value = "Maybe Human"

        lower = str(value).lower()

        if "bot" in lower:
            color = "#f59e0b"
        elif "suspicious" in lower or "block" in lower:
            color = "#ef4444"
        elif "human" in lower:
            color = "#22c55e"
        else:
            color = "#64748b"

        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            'background:{}22;color:{};font-weight:700;">{}</span>',
            color,
            color,
            value,
        )

    @admin.display(description="COUNTRY")
    def country_display(self, obj):
        return get_obj_value(obj, ["country", "country_code", "region"], "-")

    @admin.display(description="USER")
    def user_display(self, obj):
        user = get_obj_value(obj, ["user", "account", "member"], None)
        if not user or user == "-":
            return "-"
        return short_text(user, 40)

    @admin.display(description="USER AGENT")
    def ua_display(self, obj):
        ua = get_obj_value(obj, ["user_agent", "ua"], "-")
        ua_text = short_text(ua, 90)

        if looks_like_bot(str(ua)):
            return format_html(
                '<span style="color:#f59e0b;font-weight:700;">{}</span>',
                ua_text,
            )

        return ua_text

    def _bulk_update_type(self, request, queryset, value: str):
        model = self.model
        type_field = first_existing_field(
            model,
            ["type", "visitor_type", "kind", "classification"],
        )

        if not type_field:
            self.message_user(
                request,
                "이 모델에는 type/visitor_type/kind/classification 필드가 없어서 변경하지 못했습니다.",
                level=messages.WARNING,
            )
            return

        count = queryset.update(**{type_field: value})
        self.message_user(request, f"{count}개 항목을 {value}(으)로 변경했습니다.")

    @admin.action(description="선택 항목을 Human으로 표시")
    def mark_as_human(self, request, queryset):
        self._bulk_update_type(request, queryset, "Human")

    @admin.action(description="선택 항목을 Bot으로 표시")
    def mark_as_bot(self, request, queryset):
        self._bulk_update_type(request, queryset, "Bot")

    @admin.action(description="선택 항목을 Suspicious로 표시")
    def mark_as_suspicious(self, request, queryset):
        self._bulk_update_type(request, queryset, "Suspicious")

    @admin.action(description="선택 항목을 Blocked로 표시")
    def mark_as_blocked(self, request, queryset):
        model = self.model
        blocked_field = first_existing_field(model, ["is_blocked", "blocked", "should_block"])

        if blocked_field:
            count = queryset.update(**{blocked_field: True})
            self.message_user(request, f"{count}개 항목을 차단 표시했습니다.")
            return

        self._bulk_update_type(request, queryset, "Blocked")


# ============================================================
# 로그인 시도 Admin
# ============================================================

class LoginAttemptAdmin(TrafficLogAdmin):
    actions = TrafficLogAdmin.actions + ["mark_success", "mark_failed"]

    def get_list_display(self, request):
        return (
            "created_display",
            "ip_display",
            "identifier_display",
            "success_display",
            "path_display",
            "status_display",
            "ua_display",
        )

    @admin.display(description="계정/이메일/식별자")
    def identifier_display(self, obj):
        return short_text(
            get_obj_value(
                obj,
                ["username", "email", "identifier", "login", "account_name"],
                "-",
            ),
            60,
        )

    @admin.display(description="성공 여부")
    def success_display(self, obj):
        value = get_obj_value(obj, ["success", "is_success", "passed", "result"], None)

        if value is True or str(value).lower() in ["success", "true", "ok", "passed"]:
            return format_html('<span style="color:#22c55e;font-weight:700;">SUCCESS</span>')

        if value is False or str(value).lower() in ["fail", "failed", "false", "error"]:
            return format_html('<span style="color:#ef4444;font-weight:700;">FAILED</span>')

        return "-"

    @admin.action(description="선택 항목을 로그인 성공으로 표시")
    def mark_success(self, request, queryset):
        field = first_existing_field(self.model, ["success", "is_success", "passed"])
        if not field:
            self.message_user(request, "success/is_success/passed 필드가 없습니다.", messages.WARNING)
            return
        count = queryset.update(**{field: True})
        self.message_user(request, f"{count}개 항목을 성공으로 변경했습니다.")

    @admin.action(description="선택 항목을 로그인 실패로 표시")
    def mark_failed(self, request, queryset):
        field = first_existing_field(self.model, ["success", "is_success", "passed"])
        if not field:
            self.message_user(request, "success/is_success/passed 필드가 없습니다.", messages.WARNING)
            return
        count = queryset.update(**{field: False})
        self.message_user(request, f"{count}개 항목을 실패로 변경했습니다.")


# ============================================================
# IP 차단/허용 규칙 Admin
# ============================================================

class BlockRuleAdmin(admin.ModelAdmin):
    list_per_page = 50
    actions = ["enable_rules", "disable_rules"]

    def get_list_display(self, request):
        return (
            "ip_display",
            "reason_display",
            "enabled_display",
            "created_display",
        )

    def get_search_fields(self, request):
        model = self.model
        candidates = [
            "ip_address",
            "ip",
            "cidr",
            "reason",
            "memo",
            "note",
            "user_agent",
        ]
        return tuple(name for name in candidates if name in field_names(model))

    def get_list_filter(self, request):
        model = self.model
        candidates = ["is_active", "active", "enabled", "created_at"]
        return tuple(name for name in candidates if name in field_names(model))

    def get_readonly_fields(self, request, obj=None):
        names = field_names(self.model)
        return tuple(name for name in ["created_at", "updated_at"] if name in names)

    def get_ordering(self, request):
        if "created_at" in field_names(self.model):
            return ("-created_at",)
        return ("-pk",)

    @admin.display(description="IP / CIDR")
    def ip_display(self, obj):
        ip = get_obj_value(obj, ["ip_address", "ip", "cidr"], "-")
        return format_html("<strong>{}</strong>", ip)

    @admin.display(description="사유")
    def reason_display(self, obj):
        return short_text(get_obj_value(obj, ["reason", "memo", "note"], "-"), 80)

    @admin.display(description="활성")
    def enabled_display(self, obj):
        value = get_obj_value(obj, ["is_active", "active", "enabled"], None)

        if value is True:
            return format_html('<span style="color:#22c55e;font-weight:700;">ON</span>')
        if value is False:
            return format_html('<span style="color:#ef4444;font-weight:700;">OFF</span>')

        return "-"

    @admin.display(description="생성일")
    def created_display(self, obj):
        value = get_obj_value(obj, ["created_at", "timestamp"], None)
        if not value:
            return "-"
        try:
            return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    @admin.action(description="선택 차단 규칙 활성화")
    def enable_rules(self, request, queryset):
        field = first_existing_field(self.model, ["is_active", "active", "enabled"])
        if not field:
            self.message_user(request, "is_active/active/enabled 필드가 없습니다.", messages.WARNING)
            return
        count = queryset.update(**{field: True})
        self.message_user(request, f"{count}개 규칙을 활성화했습니다.")

    @admin.action(description="선택 차단 규칙 비활성화")
    def disable_rules(self, request, queryset):
        field = first_existing_field(self.model, ["is_active", "active", "enabled"])
        if not field:
            self.message_user(request, "is_active/active/enabled 필드가 없습니다.", messages.WARNING)
            return
        count = queryset.update(**{field: False})
        self.message_user(request, f"{count}개 규칙을 비활성화했습니다.")


# ============================================================
# 모델 자동 등록
# ============================================================

TRAFFIC_MODEL_NAMES = [
    "VisitorLog",
    "VisitLog",
    "PageViewLog",
    "PageviewLog",
    "RequestLog",
    "TrafficLog",
    "BotVisitLog",
    "BlockedRequestLog",
    "SecurityEvent",
]

LOGIN_MODEL_NAMES = [
    "LoginAttempt",
    "LoginAttemptLog",
    "AuthAttempt",
    "AuthAttemptLog",
]

BLOCK_MODEL_NAMES = [
    "BlockedIP",
    "IPBlock",
    "IPBlockRule",
    "BotBlockRule",
    "SecurityBlockRule",
]


def safe_register(model_name: str, admin_class: type[admin.ModelAdmin]):
    model = get_model_if_exists(model_name)
    if model is None:
        return

    try:
        admin.site.register(model, admin_class)
    except AlreadyRegistered:
        pass


for model_name in TRAFFIC_MODEL_NAMES:
    safe_register(model_name, TrafficLogAdmin)

for model_name in LOGIN_MODEL_NAMES:
    safe_register(model_name, LoginAttemptAdmin)

for model_name in BLOCK_MODEL_NAMES:
    safe_register(model_name, BlockRuleAdmin)
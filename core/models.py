from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class VisitorLog(models.Model):
    class VisitorType(models.TextChoices):
        HUMAN = "Human", "Human"
        MAYBE_HUMAN = "Maybe Human", "Maybe Human"
        BOT = "Bot", "Bot"
        SUSPICIOUS = "Suspicious", "Suspicious"
        BLOCKED = "Blocked", "Blocked"

    visit_date = models.DateField(default=timezone.localdate, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)

    country = models.CharField(max_length=80, default="Unknown", blank=True)
    type = models.CharField(
        max_length=30,
        choices=VisitorType.choices,
        default=VisitorType.MAYBE_HUMAN,
        db_index=True,
    )

    path = models.TextField(blank=True, default="")
    method = models.CharField(max_length=12, blank=True, default="GET")
    user_agent = models.TextField(blank=True, default="")
    referer = models.TextField(blank=True, default="")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visitor_logs",
    )

    request_count = models.PositiveIntegerField(default=1)
    is_bot = models.BooleanField(default=False, db_index=True)
    is_blocked = models.BooleanField(default=False, db_index=True)

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "방문자 로그"
        verbose_name_plural = "방문자 로그"
        indexes = [
            models.Index(fields=["visit_date", "ip_address"]),
            models.Index(fields=["type", "visit_date"]),
            models.Index(fields=["is_bot", "visit_date"]),
            models.Index(fields=["is_blocked", "visit_date"]),
        ]
        unique_together = ("visit_date", "ip_address")

    def __str__(self):
        return f"{self.visit_date} / {self.ip_address} / {self.type}"


class PageViewLog(models.Model):
    class VisitorType(models.TextChoices):
        HUMAN = "Human", "Human"
        MAYBE_HUMAN = "Maybe Human", "Maybe Human"
        BOT = "Bot", "Bot"
        SUSPICIOUS = "Suspicious", "Suspicious"
        BLOCKED = "Blocked", "Blocked"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    country = models.CharField(max_length=80, default="Unknown", blank=True)

    method = models.CharField(max_length=12, blank=True, default="GET")
    path = models.TextField(db_index=False)
    query_string = models.TextField(blank=True, default="")
    referer = models.TextField(blank=True, default="")
    user_agent = models.TextField(blank=True, default="")

    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    type = models.CharField(
        max_length=30,
        choices=VisitorType.choices,
        default=VisitorType.MAYBE_HUMAN,
        db_index=True,
    )

    is_bot = models.BooleanField(default=False, db_index=True)
    is_suspicious = models.BooleanField(default=False, db_index=True)
    is_blocked = models.BooleanField(default=False, db_index=True)

    response_ms = models.PositiveIntegerField(null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pageview_logs",
    )

    class Meta:
        verbose_name = "페이지뷰 로그"
        verbose_name_plural = "페이지뷰 로그"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["status_code", "created_at"]),
            models.Index(fields=["type", "created_at"]),
            models.Index(fields=["is_blocked", "created_at"]),
        ]

    def __str__(self):
        return f"{self.ip_address} / {self.status_code} / {self.path[:60]}"


class RequestLog(models.Model):
    class VisitorType(models.TextChoices):
        HUMAN = "Human", "Human"
        MAYBE_HUMAN = "Maybe Human", "Maybe Human"
        BOT = "Bot", "Bot"
        SUSPICIOUS = "Suspicious", "Suspicious"
        BLOCKED = "Blocked", "Blocked"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    method = models.CharField(max_length=12, blank=True, default="GET")
    path = models.TextField()
    full_path = models.TextField(blank=True, default="")
    referer = models.TextField(blank=True, default="")
    user_agent = models.TextField(blank=True, default="")

    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    type = models.CharField(
        max_length=30,
        choices=VisitorType.choices,
        default=VisitorType.MAYBE_HUMAN,
        db_index=True,
    )

    is_bot = models.BooleanField(default=False, db_index=True)
    is_suspicious = models.BooleanField(default=False, db_index=True)
    is_blocked = models.BooleanField(default=False, db_index=True)

    response_ms = models.PositiveIntegerField(null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="request_logs",
    )

    class Meta:
        verbose_name = "요청 로그"
        verbose_name_plural = "요청 로그"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["status_code", "created_at"]),
            models.Index(fields=["is_bot", "created_at"]),
            models.Index(fields=["is_blocked", "created_at"]),
        ]

    def __str__(self):
        return f"{self.ip_address} / {self.method} / {self.status_code} / {self.path[:80]}"


class LoginAttemptLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    path = models.TextField(blank=True, default="")
    method = models.CharField(max_length=12, blank=True, default="GET")

    username = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    identifier = models.CharField(max_length=255, blank=True, default="")

    success = models.BooleanField(null=True, blank=True, db_index=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    user_agent = models.TextField(blank=True, default="")
    referer = models.TextField(blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="login_attempt_logs",
    )

    class Meta:
        verbose_name = "로그인 시도 로그"
        verbose_name_plural = "로그인 시도 로그"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["success", "created_at"]),
            models.Index(fields=["status_code", "created_at"]),
        ]

    def __str__(self):
        result = "UNKNOWN" if self.success is None else ("SUCCESS" if self.success else "FAILED")
        return f"{self.ip_address} / {result} / {self.identifier or self.email or self.username}"


class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(
        unique=True,
        help_text="단일 IP 차단용. 예: 74.7.227.45",
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "차단 IP"
        verbose_name_plural = "차단 IP"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        status = "ON" if self.is_active else "OFF"
        return f"{self.ip_address} / {status}"


class IPBlockRule(models.Model):
    cidr = models.CharField(
        max_length=64,
        unique=True,
        help_text="CIDR 대역 차단용. 예: 57.141.14.0/24",
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "IP 대역 차단 규칙"
        verbose_name_plural = "IP 대역 차단 규칙"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        status = "ON" if self.is_active else "OFF"
        return f"{self.cidr} / {status}"


class SecurityEvent(models.Model):
    class Severity(models.TextChoices):
        INFO = "INFO", "INFO"
        WARNING = "WARNING", "WARNING"
        DANGER = "DANGER", "DANGER"
        CRITICAL = "CRITICAL", "CRITICAL"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    event_type = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
        db_index=True,
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    method = models.CharField(max_length=12, blank=True, default="GET")
    path = models.TextField(blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    user_agent = models.TextField(blank=True, default="")
    referer = models.TextField(blank=True, default="")
    message = models.TextField(blank=True, default="")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )

    class Meta:
        verbose_name = "보안 이벤트"
        verbose_name_plural = "보안 이벤트"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self):
        return f"{self.severity} / {self.event_type} / {self.ip_address}"
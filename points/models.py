from django.conf import settings
from django.db import models
from django.utils import timezone


class PointTransaction(models.Model):
    class TransactionType(models.TextChoices):
        EARN = "earn", "적립"
        SPEND = "spend", "사용"
        REFUND = "refund", "환불"
        ADMIN = "admin", "관리자 조정"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_transactions",
    )
    amount = models.IntegerField()
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
    )
    reason = models.CharField(max_length=120)
    memo = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "포인트 내역"
        verbose_name_plural = "포인트 내역"

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.user} {sign}{self.amount}P - {self.reason}"


class RewardItem(models.Model):
    class RewardType(models.TextChoices):
        CULTURE = "culture", "문화상품권"
        STARBUCKS = "starbucks", "스타벅스"
        CU = "cu", "CU"
        ETC = "etc", "기타"

    reward_type = models.CharField(
        max_length=30,
        choices=RewardType.choices,
        default=RewardType.ETC,
    )
    name = models.CharField(max_length=80)
    brand = models.CharField(max_length=40, blank=True, default="")
    face_value = models.PositiveIntegerField(default=0, help_text="실제 권면가 또는 예상 구매가")
    required_points = models.PositiveIntegerField()
    emoji = models.CharField(max_length=8, default="🎁")
    description = models.CharField(max_length=180, blank=True, default="")
    notice = models.TextField(blank=True, default="")
    stock = models.PositiveIntegerField(default=0, help_text="0이면 품절")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "required_points", "id"]
        verbose_name = "포인트샵 상품"
        verbose_name_plural = "포인트샵 상품"

    def __str__(self):
        return f"{self.name} - {self.required_points}P"

    @property
    def is_sold_out(self):
        return self.stock <= 0


class RewardRedemption(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "신청중"
        APPROVED = "approved", "승인완료"
        SENT = "sent", "발송완료"
        REJECTED = "rejected", "반려"
        CANCELED = "canceled", "취소"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_redemptions",
    )
    item = models.ForeignKey(
        RewardItem,
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    points_spent = models.PositiveIntegerField()
    recipient_email = models.EmailField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    coupon_code = models.TextField(blank=True, default="", help_text="쿠폰번호/PIN/발송 메모")
    admin_note = models.TextField(blank=True, default="")
    user_notice_read_at = models.DateTimeField(null=True, blank=True)
    is_refunded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "쿠폰 교환 신청"
        verbose_name_plural = "쿠폰 교환 신청"

    def __str__(self):
        return f"{self.user} - {self.item.name} - {self.get_status_display()}"

    @property
    def should_show_notice(self):
        return self.status in [self.Status.SENT, self.Status.REJECTED] and not self.user_notice_read_at


class AdRewardCampaign(models.Model):
    title = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=120, blank=True, default="")
    reward_points = models.PositiveIntegerField(default=30)
    daily_limit = models.PositiveIntegerField(default=3)
    emoji = models.CharField(max_length=8, default="📺")
    ad_slot_key = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "광고 포인트 캠페인"
        verbose_name_plural = "광고 포인트 캠페인"

    def __str__(self):
        return f"{self.title} +{self.reward_points}P"


class AdRewardClaim(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "확인중"
        APPROVED = "approved", "지급완료"
        REJECTED = "rejected", "반려"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ad_reward_claims",
    )
    campaign = models.ForeignKey(
        AdRewardCampaign,
        on_delete=models.PROTECT,
        related_name="claims",
    )
    points = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_note = models.TextField(blank=True, default="")
    user_notice_read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "광고 포인트 신청"
        verbose_name_plural = "광고 포인트 신청"

    def __str__(self):
        return f"{self.user} - {self.campaign.title} - {self.get_status_display()}"

    @property
    def should_show_notice(self):
        return self.status in [self.Status.APPROVED, self.Status.REJECTED] and not self.user_notice_read_at

    @classmethod
    def today_count(cls, user, campaign):
        today = timezone.localdate()
        return cls.objects.filter(
            user=user,
            campaign=campaign,
            created_at__date=today,
        ).count()
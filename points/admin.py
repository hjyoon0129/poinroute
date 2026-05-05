from django import forms
from django.contrib import admin
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Profile

from .models import (
    AdRewardCampaign,
    AdRewardClaim,
    PointTransaction,
    RewardItem,
    RewardRedemption,
)
from .services import (
    approve_ad_reward_claim,
    reject_redemption_and_refund,
    send_reward_email,
)


def _profile_field_names():
    return {field.name for field in Profile._meta.get_fields()}


def _get_profile_for_update(user):
    profile, _ = Profile.objects.select_for_update().get_or_create(user=user)
    return profile


def _normalize_transaction_amount(transaction_type, amount):
    amount = int(amount)

    if transaction_type == PointTransaction.TransactionType.SPEND:
        return -abs(amount)

    if transaction_type in [
        PointTransaction.TransactionType.EARN,
        PointTransaction.TransactionType.REFUND,
    ]:
        return abs(amount)

    # ADMIN은 양수면 지급, 음수면 차감으로 사용 가능
    return amount


def _apply_point_transaction_to_profile(point_transaction):
    """
    관리자에서 PointTransaction을 직접 생성할 때 실제 Profile.points에 반영한다.
    기존 거래내역 수정 시에는 호출하지 않는다.
    """
    user = point_transaction.user
    amount = int(point_transaction.amount)

    profile = _get_profile_for_update(user)
    current_points = getattr(profile, "points", 0) or 0

    next_points = current_points + amount

    if next_points < 0:
        raise ValueError("사용자의 포인트가 0P 미만이 될 수 없습니다.")

    profile.points = next_points

    update_fields = ["points"]
    fields = _profile_field_names()

    # 관리자 지급/일반 적립은 누적 획득 포인트에도 반영
    # 환불은 누적 획득 포인트로 보지 않음
    if (
        amount > 0
        and "total_earned_points" in fields
        and point_transaction.transaction_type
        in [
            PointTransaction.TransactionType.EARN,
            PointTransaction.TransactionType.ADMIN,
        ]
    ):
        profile.total_earned_points = (
            getattr(profile, "total_earned_points", 0) or 0
        ) + amount
        update_fields.append("total_earned_points")

    if "updated_at" in fields:
        update_fields.append("updated_at")

    profile.save(update_fields=list(dict.fromkeys(update_fields)))


class PointTransactionAdminForm(forms.ModelForm):
    class Meta:
        model = PointTransaction
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        user = cleaned_data.get("user")
        amount = cleaned_data.get("amount")
        transaction_type = cleaned_data.get("transaction_type")

        if not user or amount is None or not transaction_type:
            return cleaned_data

        amount = int(amount)

        if amount == 0:
            raise forms.ValidationError("포인트는 0P로 입력할 수 없습니다.")

        if transaction_type == PointTransaction.TransactionType.EARN and amount < 0:
            raise forms.ValidationError("적립은 양수 포인트로 입력해주세요.")

        if transaction_type == PointTransaction.TransactionType.REFUND and amount < 0:
            raise forms.ValidationError("환불은 양수 포인트로 입력해주세요.")

        signed_amount = _normalize_transaction_amount(transaction_type, amount)

        try:
            current_points = getattr(user.profile, "points", 0) or 0
        except Profile.DoesNotExist:
            current_points = 0

        if current_points + signed_amount < 0:
            raise forms.ValidationError(
                f"현재 포인트가 {current_points}P라서 {abs(signed_amount)}P를 차감할 수 없습니다."
            )

        return cleaned_data


@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    form = PointTransactionAdminForm

    list_display = (
        "id",
        "user_display",
        "amount_display",
        "transaction_type",
        "reason",
        "user_current_points_display",
        "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "reason",
        "memo",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    fieldsets = (
        (
            "포인트 지급/차감",
            {
                "fields": (
                    "user",
                    "transaction_type",
                    "amount",
                    "reason",
                    "memo",
                ),
                "description": (
                    "관리자가 특정 사용자에게 포인트를 지급하려면 "
                    "거래 유형을 '관리자 조정' 또는 '적립'으로 선택하고 양수 포인트를 입력하세요. "
                    "관리자 조정에서 음수를 입력하면 차감으로 처리됩니다."
                ),
            },
        ),
        (
            "기록",
            {
                "fields": ("created_at",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "user",
                "transaction_type",
                "amount",
                "reason",
                "memo",
                "created_at",
            )

        return ("created_at",)

    def get_changeform_initial_data(self, request):
        return {
            "transaction_type": PointTransaction.TransactionType.ADMIN,
            "reason": "관리자 포인트 지급",
            "memo": "",
        }

    def has_delete_permission(self, request, obj=None):
        # 포인트 장부는 삭제하지 않고 보정 거래를 추가하는 방식으로 운영
        return False

    def save_model(self, request, obj, form, change):
        if change:
            # 기존 포인트 내역은 장부 보존용으로 수정하지 않음
            super().save_model(request, obj, form, change)
            return

        obj.amount = _normalize_transaction_amount(
            obj.transaction_type,
            obj.amount,
        )

        with transaction.atomic():
            _apply_point_transaction_to_profile(obj)
            super().save_model(request, obj, form, change)

        self.message_user(
            request,
            f"{obj.user} 사용자에게 {obj.amount:+,}P가 반영되었습니다.",
        )

    @admin.display(description="사용자")
    def user_display(self, obj):
        if getattr(obj.user, "email", ""):
            return f"{obj.user.username} / {obj.user.email}"

        return obj.user.username

    @admin.display(description="포인트")
    def amount_display(self, obj):
        amount = obj.amount or 0

        if amount > 0:
            return f"+{amount:,}P"

        return f"{amount:,}P"

    @admin.display(description="현재 보유 포인트")
    def user_current_points_display(self, obj):
        try:
            points = obj.user.profile.points or 0
        except Profile.DoesNotExist:
            points = 0

        return f"{points:,}P"


@admin.register(RewardItem)
class RewardItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "emoji",
        "name",
        "reward_type",
        "face_value",
        "required_points",
        "stock",
        "is_active",
        "display_order",
    )
    list_editable = (
        "required_points",
        "stock",
        "is_active",
        "display_order",
    )
    list_filter = ("reward_type", "is_active")
    search_fields = ("name", "brand", "description")
    ordering = ("display_order", "required_points")


@admin.register(RewardRedemption)
class RewardRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "item",
        "points_spent",
        "recipient_email",
        "status",
        "is_refunded",
        "created_at",
        "processed_at",
        "sent_at",
    )
    list_filter = ("status", "is_refunded", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "recipient_email",
        "item__name",
        "coupon_code",
        "admin_note",
    )
    readonly_fields = (
        "user",
        "item",
        "points_spent",
        "created_at",
        "processed_at",
        "sent_at",
        "user_notice_read_at",
        "is_refunded",
    )
    actions = (
        "approve_selected",
        "reject_selected_and_refund",
        "mark_sent_and_email",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (
            "신청 정보",
            {
                "fields": (
                    "user",
                    "item",
                    "points_spent",
                    "recipient_email",
                    "status",
                )
            },
        ),
        (
            "지급 정보",
            {
                "fields": (
                    "coupon_code",
                    "admin_note",
                )
            },
        ),
        (
            "처리 기록",
            {
                "fields": (
                    "is_refunded",
                    "created_at",
                    "processed_at",
                    "sent_at",
                    "user_notice_read_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "item")

    @admin.action(description="선택 신청 승인완료 처리")
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status=RewardRedemption.Status.PENDING).update(
            status=RewardRedemption.Status.APPROVED,
            processed_at=timezone.now(),
        )

        self.message_user(request, f"{updated}건을 승인완료 처리했습니다.")

    @admin.action(description="선택 신청 반려 + 포인트 환불")
    def reject_selected_and_refund(self, request, queryset):
        count = 0

        for redemption in queryset.select_related("user", "item"):
            reject_redemption_and_refund(
                redemption,
                admin_note=redemption.admin_note or "관리자 반려 처리",
            )
            count += 1

        self.message_user(request, f"{count}건을 반려하고 포인트를 환불했습니다.")

    @admin.action(description="선택 신청 발송완료 + 이메일 발송")
    def mark_sent_and_email(self, request, queryset):
        count = 0

        for redemption in queryset.select_related("user", "item"):
            redemption.status = RewardRedemption.Status.SENT
            redemption.processed_at = redemption.processed_at or timezone.now()
            redemption.sent_at = timezone.now()
            redemption.save(update_fields=["status", "processed_at", "sent_at"])

            send_reward_email(redemption)
            count += 1

        self.message_user(
            request,
            f"{count}건을 발송완료 처리하고 이메일 발송을 시도했습니다.",
        )

    def save_model(self, request, obj, form, change):
        old_status = None

        if change and obj.pk:
            old_status = RewardRedemption.objects.get(pk=obj.pk).status

        # 반려는 super().save_model 전에 처리해야 환불 로직이 정상 작동함
        if (
            change
            and obj.status == RewardRedemption.Status.REJECTED
            and old_status != RewardRedemption.Status.REJECTED
        ):
            reject_redemption_and_refund(
                obj,
                admin_note=obj.admin_note or "관리자 반려 처리",
            )
            self.message_user(
                request,
                "쿠폰 신청을 반려하고 포인트를 환불했습니다.",
            )
            return

        if obj.status in [
            RewardRedemption.Status.APPROVED,
            RewardRedemption.Status.SENT,
        ]:
            obj.processed_at = obj.processed_at or timezone.now()

        if obj.status == RewardRedemption.Status.SENT:
            obj.sent_at = obj.sent_at or timezone.now()

        super().save_model(request, obj, form, change)

        if (
            obj.status == RewardRedemption.Status.SENT
            and old_status != RewardRedemption.Status.SENT
        ):
            send_reward_email(obj)
            self.message_user(
                request,
                "쿠폰 지급 이메일 발송을 시도했습니다.",
            )


@admin.register(AdRewardCampaign)
class AdRewardCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "emoji",
        "title",
        "reward_points",
        "daily_limit",
        "is_active",
        "display_order",
    )
    list_editable = (
        "reward_points",
        "daily_limit",
        "is_active",
        "display_order",
    )
    search_fields = ("title", "subtitle", "ad_slot_key")
    list_filter = ("is_active",)
    ordering = ("display_order", "id")


@admin.register(AdRewardClaim)
class AdRewardClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "campaign",
        "points",
        "status",
        "created_at",
        "processed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "campaign__title",
        "admin_note",
    )
    readonly_fields = (
        "user",
        "campaign",
        "points",
        "created_at",
        "processed_at",
        "user_notice_read_at",
    )
    actions = ("approve_selected", "reject_selected")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "campaign")

    @admin.action(description="선택 광고 포인트 지급")
    def approve_selected(self, request, queryset):
        count = 0

        for claim in queryset.select_related("user", "campaign"):
            if claim.status != AdRewardClaim.Status.APPROVED:
                approve_ad_reward_claim(claim)
                count += 1

        self.message_user(request, f"{count}건의 광고 포인트를 지급했습니다.")

    @admin.action(description="선택 광고 신청 반려")
    def reject_selected(self, request, queryset):
        updated = queryset.filter(status=AdRewardClaim.Status.PENDING).update(
            status=AdRewardClaim.Status.REJECTED,
            processed_at=timezone.now(),
        )

        self.message_user(request, f"{updated}건을 반려했습니다.")

    def save_model(self, request, obj, form, change):
        old_status = None

        if change and obj.pk:
            old_status = AdRewardClaim.objects.get(pk=obj.pk).status

        if (
            change
            and obj.status == AdRewardClaim.Status.APPROVED
            and old_status != AdRewardClaim.Status.APPROVED
        ):
            approve_ad_reward_claim(obj)

            if obj.admin_note:
                AdRewardClaim.objects.filter(pk=obj.pk).update(
                    admin_note=obj.admin_note,
                )

            self.message_user(
                request,
                f"{obj.points}P 광고 포인트를 지급했습니다.",
            )
            return

        if (
            change
            and obj.status == AdRewardClaim.Status.REJECTED
            and old_status != AdRewardClaim.Status.REJECTED
        ):
            AdRewardClaim.objects.filter(pk=obj.pk).update(
                status=AdRewardClaim.Status.REJECTED,
                admin_note=obj.admin_note,
                processed_at=timezone.now(),
            )

            self.message_user(request, "광고 포인트 신청을 반려했습니다.")
            return

        super().save_model(request, obj, form, change)
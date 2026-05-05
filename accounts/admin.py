from django.contrib import admin
from django.db.models import Sum

from .models import Profile
from points.models import AdRewardClaim, PointTransaction, RewardRedemption


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_display",
        "nickname_display",
        "current_points_display",
        "total_earned_points_display",
        "reward_count_display",
        "ad_claim_count_display",
    )

    ordering = ("-id",)

    def get_search_fields(self, request):
        fields = ["user__username", "user__email"]

        profile_field_names = {
            field.name
            for field in Profile._meta.get_fields()
        }

        if "nickname" in profile_field_names:
            fields.append("nickname")

        if "recovery_email" in profile_field_names:
            fields.append("recovery_email")

        return fields

    @admin.display(description="사용자")
    def user_display(self, obj):
        user = getattr(obj, "user", None)

        if not user:
            return "-"

        if getattr(user, "email", ""):
            return f"{user.username} / {user.email}"

        return user.username

    @admin.display(description="닉네임")
    def nickname_display(self, obj):
        nickname = getattr(obj, "nickname", "")

        if nickname:
            return nickname

        return "-"

    @admin.display(description="현재 포인트")
    def current_points_display(self, obj):
        points = getattr(obj, "points", 0) or 0
        return f"{points:,}P"

    @admin.display(description="누적 획득 포인트")
    def total_earned_points_display(self, obj):
        if hasattr(obj, "total_earned_points"):
            total = getattr(obj, "total_earned_points", 0) or 0
            return f"{total:,}P"

        user = getattr(obj, "user", None)

        if not user:
            return "0P"

        total = (
            PointTransaction.objects
            .filter(
                user=user,
                amount__gt=0,
            )
            .aggregate(total=Sum("amount"))
            .get("total")
            or 0
        )

        return f"{total:,}P"

    @admin.display(description="쿠폰 신청")
    def reward_count_display(self, obj):
        user = getattr(obj, "user", None)

        if not user:
            return "0건"

        count = RewardRedemption.objects.filter(user=user).count()
        return f"{count}건"

    @admin.display(description="광고포인트 신청")
    def ad_claim_count_display(self, obj):
        user = getattr(obj, "user", None)

        if not user:
            return "0건"

        count = AdRewardClaim.objects.filter(user=user).count()
        return f"{count}건"
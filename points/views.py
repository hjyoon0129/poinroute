from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    AdRewardCampaign,
    AdRewardClaim,
    PointTransaction,
    RewardItem,
    RewardRedemption,
)
from .services import request_reward_redemption


def point_shop(request):
    reward_items = RewardItem.objects.filter(is_active=True).order_by(
        "display_order",
        "required_points",
        "id",
    )

    campaigns = AdRewardCampaign.objects.filter(is_active=True).order_by(
        "display_order",
        "id",
    )

    user_points = 0
    campaign_counts = {}

    my_redemptions = RewardRedemption.objects.none()
    my_ad_claims = AdRewardClaim.objects.none()
    transactions = PointTransaction.objects.none()

    if request.user.is_authenticated:
        my_redemptions = RewardRedemption.objects.filter(
            user=request.user
        ).select_related("item")[:8]

        my_ad_claims = AdRewardClaim.objects.filter(
            user=request.user
        ).select_related("campaign")[:8]

        transactions = PointTransaction.objects.filter(user=request.user)[:12]

        today = timezone.localdate()

        campaign_counts = {
            row["campaign_id"]: row["count"]
            for row in AdRewardClaim.objects.filter(
                user=request.user,
                created_at__date=today,
            )
            .values("campaign_id")
            .annotate(count=models.Count("id"))
        }

        if hasattr(request.user, "profile"):
            user_points = request.user.profile.points or 0

    return render(
        request,
        "points/point_shop.html",
        {
            "reward_items": reward_items,
            "campaigns": campaigns,
            "my_redemptions": my_redemptions,
            "my_ad_claims": my_ad_claims,
            "transactions": transactions,
            "campaign_counts": campaign_counts,
            "user_points": user_points,
        },
    )


@login_required(login_url="/accounts/login/")
def point_history(request):
    transactions = PointTransaction.objects.filter(user=request.user)

    redemptions = RewardRedemption.objects.filter(
        user=request.user
    ).select_related("item")

    ad_claims = AdRewardClaim.objects.filter(
        user=request.user
    ).select_related("campaign")

    user_points = 0
    if hasattr(request.user, "profile"):
        user_points = request.user.profile.points or 0

    return render(
        request,
        "points/point_history.html",
        {
            "transactions": transactions,
            "redemptions": redemptions,
            "ad_claims": ad_claims,
            "user_points": user_points,
        },
    )


@require_POST
@login_required(login_url="/accounts/login/")
def redeem_reward(request, item_id):
    try:
        redemption = request_reward_redemption(request.user, item_id)

        messages.success(
            request,
            f"{redemption.item.name} 신청이 완료되었습니다. 관리자 확인 후 이메일로 지급됩니다.",
        )

    except RewardItem.DoesNotExist:
        messages.error(request, "존재하지 않는 상품입니다.")

    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("points:shop")


@require_POST
@login_required(login_url="/accounts/login/")
def claim_ad_reward(request, campaign_id):
    campaign = get_object_or_404(
        AdRewardCampaign,
        id=campaign_id,
        is_active=True,
    )

    today_count = AdRewardClaim.today_count(request.user, campaign)

    if today_count >= campaign.daily_limit:
        messages.error(
            request,
            f"오늘은 이미 {campaign.daily_limit}회 신청했습니다.",
        )
        return redirect("points:shop")

    with transaction.atomic():
        AdRewardClaim.objects.create(
            user=request.user,
            campaign=campaign,
            points=campaign.reward_points,
            status=AdRewardClaim.Status.PENDING,
        )

    messages.success(
        request,
        f"{campaign.reward_points}P 광고 보상 신청이 접수되었습니다. 확인 후 지급됩니다.",
    )

    return redirect("points:shop")


@require_POST
@login_required(login_url="/accounts/login/")
def read_reward_notice(request, redemption_id):
    RewardRedemption.objects.filter(
        id=redemption_id,
        user=request.user,
    ).update(user_notice_read_at=timezone.now())

    next_url = request.POST.get("next") or "points:shop"
    return redirect(next_url)


@require_POST
@login_required(login_url="/accounts/login/")
def read_ad_notice(request, claim_id):
    AdRewardClaim.objects.filter(
        id=claim_id,
        user=request.user,
    ).update(user_notice_read_at=timezone.now())

    next_url = request.POST.get("next") or "points:shop"
    return redirect(next_url)
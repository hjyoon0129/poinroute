from .models import AdRewardClaim, RewardRedemption


def point_notices(request):
    if not request.user.is_authenticated:
        return {
            "reward_notice": None,
            "ad_reward_notice": None,
        }

    reward_notice = RewardRedemption.objects.filter(
        user=request.user,
        user_notice_read_at__isnull=True,
        status__in=[
            RewardRedemption.Status.SENT,
            RewardRedemption.Status.REJECTED,
        ],
    ).select_related("item").first()

    ad_reward_notice = None

    if not reward_notice:
        ad_reward_notice = AdRewardClaim.objects.filter(
            user=request.user,
            user_notice_read_at__isnull=True,
            status__in=[
                AdRewardClaim.Status.APPROVED,
                AdRewardClaim.Status.REJECTED,
            ],
        ).select_related("campaign").first()

    return {
        "reward_notice": reward_notice,
        "ad_reward_notice": ad_reward_notice,
    }
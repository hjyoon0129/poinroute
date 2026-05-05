from django.core.management.base import BaseCommand

from points.models import AdRewardCampaign, RewardItem


class Command(BaseCommand):
    help = "포인루트 포인트샵 기본 상품과 광고 캠페인을 생성합니다."

    def handle(self, *args, **options):
        rewards = [
            {
                "reward_type": RewardItem.RewardType.STARBUCKS,
                "name": "스타벅스 아메리카노 Tall",
                "brand": "Starbucks",
                "face_value": 4700,
                "required_points": 7000,
                "emoji": "☕",
                "description": "스타벅스 카페 아메리카노 Tall 교환권입니다.",
                "notice": "관리자 확인 후 가입 이메일로 쿠폰번호가 발송됩니다.",
                "stock": 10,
                "display_order": 10,
            },
            {
                "reward_type": RewardItem.RewardType.CU,
                "name": "CU 모바일금액권 5천원권",
                "brand": "CU",
                "face_value": 5000,
                "required_points": 7500,
                "emoji": "🏪",
                "description": "CU 편의점에서 사용할 수 있는 모바일금액권입니다.",
                "notice": "관리자 확인 후 가입 이메일로 쿠폰번호가 발송됩니다.",
                "stock": 10,
                "display_order": 20,
            },
            {
                "reward_type": RewardItem.RewardType.CULTURE,
                "name": "문화상품권 5천원권",
                "brand": "문화상품권",
                "face_value": 5000,
                "required_points": 7500,
                "emoji": "🎫",
                "description": "도서, 영화, 온라인 사용처에서 활용 가능한 문화상품권입니다.",
                "notice": "관리자 확인 후 가입 이메일로 PIN 번호가 발송됩니다.",
                "stock": 10,
                "display_order": 30,
            },
            {
                "reward_type": RewardItem.RewardType.CULTURE,
                "name": "문화상품권 1만원권",
                "brand": "문화상품권",
                "face_value": 10000,
                "required_points": 14000,
                "emoji": "🎟️",
                "description": "포인트를 많이 모은 사용자를 위한 1만원권 상품입니다.",
                "notice": "관리자 확인 후 가입 이메일로 PIN 번호가 발송됩니다.",
                "stock": 5,
                "display_order": 40,
            },
        ]

        for data in rewards:
            item, created = RewardItem.objects.update_or_create(
                name=data["name"],
                defaults=data,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'생성' if created else '수정'}: {item.name}"
                )
            )

        campaigns = [
            {
                "title": "광고 보고 30P 받기",
                "subtitle": "짧은 광고를 보고 포인트를 신청하세요. 하루 3회까지 가능합니다.",
                "reward_points": 30,
                "daily_limit": 3,
                "emoji": "📺",
                "ad_slot_key": "demo_reward_ad_30",
                "display_order": 10,
            },
            {
                "title": "추천 광고 참여 50P",
                "subtitle": "이벤트성 광고 참여 보상입니다. 승인 후 지급됩니다.",
                "reward_points": 50,
                "daily_limit": 1,
                "emoji": "🎯",
                "ad_slot_key": "demo_event_ad_50",
                "display_order": 20,
            },
        ]

        for data in campaigns:
            campaign, created = AdRewardCampaign.objects.update_or_create(
                title=data["title"],
                defaults=data,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'생성' if created else '수정'}: {campaign.title}"
                )
            )
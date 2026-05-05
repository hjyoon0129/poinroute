from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from .models import (
    AdRewardClaim,
    PointTransaction,
    RewardItem,
    RewardRedemption,
)


def _profile_point_fields():
    return {field.name for field in Profile._meta.get_fields()}


def _get_profile_for_update(user):
    profile, _ = Profile.objects.select_for_update().get_or_create(user=user)
    return profile


def _safe_save_profile(profile, update_fields):
    fields = _profile_point_fields()

    final_fields = []
    for field in update_fields:
        if field in fields:
            final_fields.append(field)

    if "updated_at" in fields and "updated_at" not in final_fields:
        final_fields.append("updated_at")

    if final_fields:
        profile.save(update_fields=final_fields)
    else:
        profile.save()


def add_points(user, amount, reason, memo=""):
    amount = int(amount)

    if amount <= 0:
        raise ValueError("적립 포인트는 1 이상이어야 합니다.")

    with transaction.atomic():
        profile = _get_profile_for_update(user)

        current_points = getattr(profile, "points", 0) or 0
        profile.points = current_points + amount

        update_fields = ["points"]

        fields = _profile_point_fields()

        if "total_earned_points" in fields:
            current_total = getattr(profile, "total_earned_points", 0) or 0
            profile.total_earned_points = current_total + amount
            update_fields.append("total_earned_points")

        _safe_save_profile(profile, update_fields)

        tx = PointTransaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=PointTransaction.TransactionType.EARN,
            reason=reason,
            memo=memo,
        )

    return tx


def spend_points(user, amount, reason, memo=""):
    amount = int(amount)

    if amount <= 0:
        raise ValueError("사용 포인트는 1 이상이어야 합니다.")

    with transaction.atomic():
        profile = _get_profile_for_update(user)

        current_points = getattr(profile, "points", 0) or 0

        if current_points < amount:
            raise ValueError("포인트가 부족합니다.")

        profile.points = current_points - amount

        _safe_save_profile(profile, ["points"])

        tx = PointTransaction.objects.create(
            user=user,
            amount=-amount,
            transaction_type=PointTransaction.TransactionType.SPEND,
            reason=reason,
            memo=memo,
        )

    return tx


def refund_points(user, amount, reason, memo=""):
    amount = int(amount)

    if amount <= 0:
        raise ValueError("환불 포인트는 1 이상이어야 합니다.")

    with transaction.atomic():
        profile = _get_profile_for_update(user)

        current_points = getattr(profile, "points", 0) or 0
        profile.points = current_points + amount

        _safe_save_profile(profile, ["points"])

        tx = PointTransaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=PointTransaction.TransactionType.REFUND,
            reason=reason,
            memo=memo,
        )

    return tx


def award_route_approved_points(post, amount=None, reason=None, memo=""):
    """
    posts/admin.py에서 루트 승인 시 호출하는 기존 함수 호환용.

    사용 예:
    award_route_approved_points(post)

    처리:
    - post.author에게 포인트 지급
    - post.awarded_points 값이 있으면 그 값을 우선 사용
    - 없으면 기본 300P 지급
    - post에 points_awarded / is_point_awarded 같은 필드가 있으면 중복 지급 방지
    """

    if not post:
        raise ValueError("포스트 정보가 없습니다.")

    user = getattr(post, "author", None)

    if not user:
        raise ValueError("포스트 작성자를 찾을 수 없습니다.")

    post_fields = {field.name for field in post._meta.get_fields()}

    duplicate_flags = [
        "points_awarded",
        "is_point_awarded",
        "point_awarded",
        "reward_paid",
        "is_reward_paid",
    ]

    for flag in duplicate_flags:
        if flag in post_fields and getattr(post, flag, False):
            return None

    if amount is None:
        amount = getattr(post, "awarded_points", None) or 300

    amount = int(amount)

    if amount <= 0:
        return None

    if reason is None:
        title = getattr(post, "title", "")
        if title:
            reason = f"루트 승인 보상: {title}"
        else:
            reason = "루트 승인 보상"

    if not memo:
        memo = f"post_id={getattr(post, 'id', '')}"

    tx = add_points(
        user=user,
        amount=amount,
        reason=reason,
        memo=memo,
    )

    update_fields = []

    if "awarded_points" in post_fields:
        post.awarded_points = amount
        update_fields.append("awarded_points")

    for flag in duplicate_flags:
        if flag in post_fields:
            setattr(post, flag, True)
            update_fields.append(flag)
            break

    now = timezone.now()

    date_fields = [
        "point_awarded_at",
        "points_awarded_at",
        "reward_paid_at",
        "approved_point_awarded_at",
    ]

    for date_field in date_fields:
        if date_field in post_fields:
            setattr(post, date_field, now)
            update_fields.append(date_field)
            break

    if update_fields:
        post.save(update_fields=list(dict.fromkeys(update_fields)))

    return tx


def revoke_route_approved_points(post, reason=None, memo=""):
    """
    승인 포인트를 잘못 지급했을 때 회수용.
    현재 포인트가 부족하면 에러가 날 수 있음.
    """

    if not post:
        raise ValueError("포스트 정보가 없습니다.")

    user = getattr(post, "author", None)

    if not user:
        raise ValueError("포스트 작성자를 찾을 수 없습니다.")

    amount = int(getattr(post, "awarded_points", 0) or 0)

    if amount <= 0:
        return None

    if reason is None:
        title = getattr(post, "title", "")
        if title:
            reason = f"루트 승인 보상 회수: {title}"
        else:
            reason = "루트 승인 보상 회수"

    if not memo:
        memo = f"post_id={getattr(post, 'id', '')}"

    tx = spend_points(
        user=user,
        amount=amount,
        reason=reason,
        memo=memo,
    )

    post_fields = {field.name for field in post._meta.get_fields()}
    update_fields = []

    duplicate_flags = [
        "points_awarded",
        "is_point_awarded",
        "point_awarded",
        "reward_paid",
        "is_reward_paid",
    ]

    for flag in duplicate_flags:
        if flag in post_fields:
            setattr(post, flag, False)
            update_fields.append(flag)

    if update_fields:
        post.save(update_fields=list(dict.fromkeys(update_fields)))

    return tx


def request_reward_redemption(user, item_id):
    with transaction.atomic():
        item = RewardItem.objects.select_for_update().get(
            id=item_id,
            is_active=True,
        )

        if item.stock <= 0:
            raise ValueError("현재 품절된 상품입니다.")

        profile = _get_profile_for_update(user)

        current_points = getattr(profile, "points", 0) or 0

        if current_points < item.required_points:
            raise ValueError("포인트가 부족합니다.")

        item.stock -= 1
        item.save(update_fields=["stock", "updated_at"])

        profile.points = current_points - item.required_points

        _safe_save_profile(profile, ["points"])

        redemption = RewardRedemption.objects.create(
            user=user,
            item=item,
            points_spent=item.required_points,
            recipient_email=user.email or getattr(profile, "recovery_email", "") or "",
            status=RewardRedemption.Status.PENDING,
        )

        PointTransaction.objects.create(
            user=user,
            amount=-item.required_points,
            transaction_type=PointTransaction.TransactionType.SPEND,
            reason=f"포인트샵 신청: {item.name}",
            memo=f"신청번호 #{redemption.id}",
        )

    return redemption


def approve_ad_reward_claim(claim):
    with transaction.atomic():
        claim = AdRewardClaim.objects.select_for_update().select_related(
            "user",
            "campaign",
        ).get(pk=claim.pk)

        if claim.status == AdRewardClaim.Status.APPROVED:
            return claim

        claim.status = AdRewardClaim.Status.APPROVED
        claim.processed_at = timezone.now()
        claim.save(update_fields=["status", "processed_at"])

        add_points(
            claim.user,
            claim.points,
            reason=f"광고 보상: {claim.campaign.title}",
            memo=f"광고 신청번호 #{claim.id}",
        )

    return claim


def reject_ad_reward_claim(claim, admin_note=""):
    with transaction.atomic():
        claim = AdRewardClaim.objects.select_for_update().get(pk=claim.pk)

        if claim.status == AdRewardClaim.Status.REJECTED:
            return claim

        claim.status = AdRewardClaim.Status.REJECTED
        claim.admin_note = admin_note or claim.admin_note
        claim.processed_at = timezone.now()
        claim.save(update_fields=["status", "admin_note", "processed_at"])

    return claim


def reject_redemption_and_refund(redemption, admin_note=""):
    with transaction.atomic():
        redemption = RewardRedemption.objects.select_for_update().select_related(
            "user",
            "item",
        ).get(pk=redemption.pk)

        if redemption.status in [
            RewardRedemption.Status.REJECTED,
            RewardRedemption.Status.CANCELED,
        ]:
            return redemption

        if not redemption.is_refunded:
            refund_points(
                redemption.user,
                redemption.points_spent,
                reason=f"포인트샵 반려 환불: {redemption.item.name}",
                memo=f"신청번호 #{redemption.id}",
            )
            redemption.is_refunded = True

        redemption.item.stock += 1
        redemption.item.save(update_fields=["stock", "updated_at"])

        redemption.status = RewardRedemption.Status.REJECTED
        redemption.admin_note = admin_note or redemption.admin_note
        redemption.processed_at = timezone.now()
        redemption.save(
            update_fields=[
                "status",
                "admin_note",
                "processed_at",
                "is_refunded",
            ]
        )

    return redemption


def mark_redemption_sent(redemption, coupon_code=None, admin_note=""):
    with transaction.atomic():
        redemption = RewardRedemption.objects.select_for_update().select_related(
            "user",
            "item",
        ).get(pk=redemption.pk)

        if coupon_code is not None:
            redemption.coupon_code = coupon_code

        if admin_note:
            redemption.admin_note = admin_note

        redemption.status = RewardRedemption.Status.SENT
        redemption.processed_at = redemption.processed_at or timezone.now()
        redemption.sent_at = timezone.now()
        redemption.save(
            update_fields=[
                "coupon_code",
                "admin_note",
                "status",
                "processed_at",
                "sent_at",
            ]
        )

    send_reward_email(redemption)

    return redemption


def send_reward_email(redemption):
    if not redemption.recipient_email:
        return False

    subject = f"[포인루트] {redemption.item.name} 쿠폰이 지급되었습니다."

    body = f"""안녕하세요. 포인루트입니다.

신청하신 포인트샵 상품이 지급되었습니다.

상품명: {redemption.item.name}
사용 포인트: {redemption.points_spent}P

쿠폰번호/안내:
{redemption.coupon_code or "관리자가 별도 안내 예정입니다."}

감사합니다.
포인루트 드림
"""

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[redemption.recipient_email],
        fail_silently=True,
    )

    return True
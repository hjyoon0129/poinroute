from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    LEVEL_POINT_STEP = 100

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # 중요:
    # unique=True + default="" 조합은 신규 소셜 가입자 여러 명이 nickname=""로 저장될 때
    # 중복 오류를 만들 수 있다.
    # 그래서 닉네임이 없을 때는 빈 문자열이 아니라 NULL로 저장한다.
    nickname = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        default=None,
        verbose_name="닉네임",
    )

    recovery_email = models.EmailField(
        blank=True,
        default="",
        verbose_name="보호 이메일",
    )

    points = models.PositiveIntegerField(
        default=0,
        verbose_name="보유 포인트",
    )

    total_earned_points = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="누적 획득 포인트",
        help_text="포인트를 사용해도 줄어들지 않는 누적 포인트입니다. 레벨 계산에 사용됩니다.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="생성일",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        verbose_name = "프로필"
        verbose_name_plural = "프로필"
        indexes = [
            models.Index(fields=["points"]),
            models.Index(fields=["total_earned_points"]),
        ]

    def save(self, *args, **kwargs):
        """
        1. 닉네임이 빈 문자열이면 NULL로 저장한다.
           - unique=True 상태에서 빈 문자열 중복 충돌을 막기 위함.
           - 카카오/구글/네이버 신규 가입자가 닉네임 없이 생성돼도 안전하다.

        2. 기존 코드 어딘가에서 profile.points만 증가시켜도
           증가분만큼 total_earned_points가 같이 올라가도록 보정한다.

        3. 포인트를 사용해서 points가 감소해도
           total_earned_points는 줄어들지 않는다.
        """

        if self.nickname is not None:
            cleaned_nickname = str(self.nickname).strip()
            self.nickname = cleaned_nickname or None

        if self.pk:
            old_data = (
                Profile.objects
                .filter(pk=self.pk)
                .values("points", "total_earned_points")
                .first()
            )

            if old_data:
                old_points = old_data.get("points") or 0
                old_total_earned_points = old_data.get("total_earned_points") or 0

                new_points = self.points or 0
                new_total_earned_points = self.total_earned_points or 0

                if new_points > old_points:
                    gained_points = new_points - old_points
                    self.total_earned_points = max(
                        new_total_earned_points,
                        old_total_earned_points + gained_points,
                    )

                if self.total_earned_points < self.points:
                    self.total_earned_points = self.points
        else:
            if self.total_earned_points < self.points:
                self.total_earned_points = self.points

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)

            if "points" in update_fields:
                update_fields.add("total_earned_points")

            if "nickname" in update_fields:
                update_fields.add("updated_at")

            kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

    @property
    def level(self):
        total_points = self.total_earned_points or 0
        return (total_points // self.LEVEL_POINT_STEP) + 1

    @property
    def level_name(self):
        return f"Lv.{self.level}"

    @property
    def current_level_start_points(self):
        return (self.level - 1) * self.LEVEL_POINT_STEP

    @property
    def next_level_points(self):
        return self.level * self.LEVEL_POINT_STEP

    @property
    def level_progress_points(self):
        total_points = self.total_earned_points or 0
        return max(0, total_points - self.current_level_start_points)

    @property
    def level_required_points(self):
        return self.LEVEL_POINT_STEP

    @property
    def level_progress_percent(self):
        if self.level_required_points <= 0:
            return 0

        percent = int((self.level_progress_points / self.level_required_points) * 100)
        return max(0, min(percent, 100))

    def add_points(self, amount, save=True):
        amount = int(amount or 0)

        if amount <= 0:
            return

        self.points = (self.points or 0) + amount
        self.total_earned_points = (self.total_earned_points or 0) + amount

        if save:
            self.save(update_fields=["points", "total_earned_points", "updated_at"])

    def spend_points(self, amount, save=True):
        amount = int(amount or 0)

        if amount <= 0:
            return True, ""

        current_points = self.points or 0

        if current_points < amount:
            return False, f"포인트가 부족합니다. 필요 포인트: {amount}P"

        self.points = current_points - amount

        if save:
            self.save(update_fields=["points", "updated_at"])

        return True, ""

    def display_name(self):
        nickname = (self.nickname or "").strip()

        if nickname:
            return nickname

        if self.user.username:
            return self.user.username

        if self.user.email:
            return self.user.email.split("@")[0]

        return f"user{self.user_id}"

    def __str__(self):
        return self.display_name()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    Profile.objects.get_or_create(user=instance)
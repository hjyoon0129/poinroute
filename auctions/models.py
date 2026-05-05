from django.conf import settings
from django.db import models
from django.utils import timezone


class AuctionRequest(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "모집중"
        SELECTED = "selected", "채택완료"
        CANCELED = "canceled", "취소됨"
        REFUNDED = "refunded", "환불됨"

    class Transport(models.TextChoices):
        ANY = "any", "상관없음"
        WALK = "walk", "뚜벅이"
        CAR = "car", "자차"
        PUBLIC = "public", "대중교통"
        RENT = "rent", "렌트카"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auction_requests",
        verbose_name="의뢰자",
    )

    title = models.CharField(
        max_length=120,
        verbose_name="의뢰 제목",
    )

    start_area = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="출발지",
        help_text="예: 인천 청라, 서울역, 부산 해운대",
    )

    destination = models.CharField(
        max_length=80,
        verbose_name="목적지",
        help_text="예: 강릉, 제주, 전주",
    )

    travel_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="여행 예정일",
    )

    people_count = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="인원",
    )

    transport = models.CharField(
        max_length=20,
        choices=Transport.choices,
        default=Transport.ANY,
        verbose_name="이동수단",
    )

    budget = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="예산",
        help_text="예: 총 20만원, 1인 5만원",
    )

    request_detail = models.TextField(
        verbose_name="요청 내용",
        help_text="원하는 여행 스타일, 피하고 싶은 장소, 꼭 가고 싶은 곳 등을 적어주세요.",
    )

    reward_points = models.PositiveIntegerField(
        verbose_name="채택 보상 포인트",
        help_text="답변 채택 시 채택자에게 지급될 포인트입니다.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="상태",
    )

    deadline_at = models.DateTimeField(
        verbose_name="마감 시간",
    )

    selected_answer = models.ForeignKey(
        "AuctionAnswer",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_for_requests",
        verbose_name="채택 답변",
    )

    selected_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="채택일",
    )

    refunded_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="환불일",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="노출 여부",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="작성일",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        verbose_name = "루트 의뢰"
        verbose_name_plural = "루트 의뢰"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["destination", "-created_at"]),
            models.Index(fields=["deadline_at"]),
            models.Index(fields=["reward_points"]),
        ]

    def __str__(self):
        return self.title

    @property
    def author_nickname(self):
        try:
            nickname = self.author.profile.nickname
            if nickname:
                return nickname
        except Exception:
            pass

        if self.author.username:
            return self.author.username

        if self.author.email:
            return self.author.email

        return "여행자"

    @property
    def is_open(self):
        return self.status == self.Status.OPEN and self.is_active

    @property
    def is_deadline_passed(self):
        return self.deadline_at <= timezone.now()

    @property
    def can_receive_answers(self):
        return self.is_open and not self.is_deadline_passed

    @property
    def active_answer_count(self):
        return self.answers.filter(is_active=True).count()


class AuctionAnswer(models.Model):
    request = models.ForeignKey(
        AuctionRequest,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="의뢰",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auction_answers",
        verbose_name="답변자",
    )

    title = models.CharField(
        max_length=120,
        verbose_name="코스 제목",
    )

    summary = models.CharField(
        max_length=180,
        blank=True,
        verbose_name="한 줄 요약",
    )

    total_time = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="예상 소요 시간",
    )

    total_cost = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="예상 비용",
    )

    content = models.TextField(
        verbose_name="상세 코스",
        help_text="시간대별 일정, 추천 이유, 이동 팁을 자세히 적어주세요.",
    )

    is_selected = models.BooleanField(
        default=False,
        verbose_name="채택 여부",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="노출 여부",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="작성일",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        verbose_name = "루트 의뢰 답변"
        verbose_name_plural = "루트 의뢰 답변"
        ordering = ["-is_selected", "created_at"]
        indexes = [
            models.Index(fields=["request", "is_active", "created_at"]),
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["is_selected"]),
        ]

    def __str__(self):
        return self.title

    @property
    def author_nickname(self):
        try:
            nickname = self.author.profile.nickname
            if nickname:
                return nickname
        except Exception:
            pass

        if self.author.username:
            return self.author.username

        if self.author.email:
            return self.author.email

        return "여행자"
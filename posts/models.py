from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q


class Post(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "검수중"
        APPROVED = "approved", "승인됨"
        NEEDS_EDIT = "needs_edit", "수정요청"
        REJECTED = "rejected", "반려됨"

    THEME_CHOICES = [
        ("couple", "👩‍❤️‍👨 커플 여행"),
        ("family", "👨‍👩‍👧‍👦 가족/부모님과"),
        ("solo", "🚶 나홀로 뚜벅이"),
        ("friends", "👯 친구와 함께"),
        ("drive", "🚗 드라이브/렌트카"),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="travel_posts",
        verbose_name="작성자",
    )

    title = models.CharField(
        max_length=100,
        verbose_name="루트 제목",
    )

    theme = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default="couple",
        verbose_name="여행 테마",
    )

    thumbnail = models.ImageField(
        upload_to="post_thumbnails/",
        blank=True,
        null=True,
        verbose_name="대표 이미지",
    )

    start_region = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="출발 시/도",
    )

    start_district = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="출발 군/구",
    )

    start_neighborhood = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="출발 동/읍/면",
    )

    start_time = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="출발 시간",
    )

    start_place_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="출발지 지도 위치",
    )

    start_latitude = models.DecimalField(
        max_digits=18,
        decimal_places=15,
        null=True,
        blank=True,
        verbose_name="출발지 위도",
    )

    start_longitude = models.DecimalField(
        max_digits=18,
        decimal_places=15,
        null=True,
        blank=True,
        verbose_name="출발지 경도",
    )

    destination = models.CharField(
        max_length=50,
        verbose_name="대표 목적지",
    )

    travel_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="여행 시작일",
    )

    travel_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="여행 종료일",
    )

    total_cost = models.IntegerField(
        default=0,
        verbose_name="총 예상 경비",
    )

    total_time = models.CharField(
        max_length=50,
        default="0시간 0분",
        verbose_name="총 예상 소요시간",
    )

    views = models.PositiveIntegerField(
        default=0,
        verbose_name="조회수",
    )

    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
        verbose_name="검수 상태",
    )

    review_note = models.TextField(
        blank=True,
        default="",
        verbose_name="검수 메모",
        help_text="수정 요청이나 반려 사유를 적어두는 관리자용 메모입니다.",
    )

    review_notice_read = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="검수 결과 알림 확인 여부",
        help_text="False이면 작성자 로그인 시 검수 결과 모달이 표시됩니다.",
    )

    points_awarded = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="포인트 지급 여부",
    )

    awarded_points = models.PositiveIntegerField(
        default=0,
        verbose_name="지급 포인트",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_travel_posts",
        verbose_name="검수자",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="검수일",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="작성일",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "여행 루트"
        verbose_name_plural = "여행 루트"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["theme"]),
            models.Index(fields=["views"]),
            models.Index(fields=["review_status"]),
            models.Index(fields=["review_notice_read"]),
            models.Index(fields=["points_awarded"]),
            models.Index(fields=["start_region", "start_district", "start_neighborhood"]),
        ]

    def __str__(self):
        return self.title

    @property
    def author_nickname(self):
        if not self.author:
            return "익명 여행자"

        profile = getattr(self.author, "profile", None)

        if profile and profile.nickname:
            return profile.nickname

        if self.author.username:
            return self.author.username

        if self.author.email:
            return self.author.email.split("@")[0]

        return f"user{self.author_id}"

    @property
    def author_level(self):
        if not self.author:
            return 1

        profile = getattr(self.author, "profile", None)

        if not profile:
            return 1

        return getattr(profile, "level", 1) or 1

    @property
    def author_level_name(self):
        return f"Lv.{self.author_level}"

    @property
    def is_review_pending(self):
        return self.review_status == self.ReviewStatus.PENDING

    @property
    def is_approved(self):
        return self.review_status == self.ReviewStatus.APPROVED

    @property
    def has_review_result(self):
        return self.review_status in [
            self.ReviewStatus.APPROVED,
            self.ReviewStatus.NEEDS_EDIT,
            self.ReviewStatus.REJECTED,
        ]

    @property
    def active_reviews(self):
        return (
            self.reviews
            .filter(is_active=True)
            .select_related("user", "user__profile")
            .order_by("-created_at")
        )

    @property
    def rating_count(self):
        return self.reviews.filter(is_active=True).count()

    @property
    def rating_avg(self):
        result = self.reviews.filter(is_active=True).aggregate(avg=Avg("rating"))
        avg = result.get("avg")

        if avg is None:
            return 0

        return round(float(avg), 1)

    @property
    def rating_avg_display(self):
        if self.rating_count <= 0:
            return "0.0"

        return f"{self.rating_avg:.1f}"

    @property
    def rating_percent(self):
        if self.rating_count <= 0:
            return 0

        return min(100, max(0, round((self.rating_avg / 5) * 100, 1)))

    @property
    def has_rating(self):
        return self.rating_count > 0


class Place(models.Model):
    post = models.ForeignKey(
        Post,
        related_name="places",
        on_delete=models.CASCADE,
    )

    day = models.IntegerField(
        default=1,
        verbose_name="일차",
    )

    visit_time_str = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="방문 시간",
    )

    place_name = models.CharField(
        max_length=100,
        verbose_name="장소명",
    )

    latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="위도",
    )

    longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="경도",
    )

    cost = models.IntegerField(
        default=0,
        verbose_name="경비",
    )

    description = models.TextField(
        blank=True,
        default="",
        verbose_name="설명",
    )

    image = models.ImageField(
        upload_to="places/",
        blank=True,
        null=True,
        verbose_name="장소 이미지",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="생성일",
    )

    class Meta:
        ordering = ["day", "id"]
        verbose_name = "방문 장소"
        verbose_name_plural = "방문 장소"
        indexes = [
            models.Index(fields=["day", "id"]),
            models.Index(fields=["place_name"]),
        ]

    def __str__(self):
        return self.place_name


class PostView(models.Model):
    post = models.ForeignKey(
        Post,
        related_name="view_logs",
        on_delete=models.CASCADE,
    )

    ip_address = models.GenericIPAddressField()
    viewed_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "루트 조회 기록"
        verbose_name_plural = "루트 조회 기록"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "ip_address", "viewed_on"],
                name="unique_post_view_per_ip_per_day",
            )
        ]
        indexes = [
            models.Index(fields=["post", "ip_address", "viewed_on"]),
            models.Index(fields=["viewed_on"]),
        ]

    def __str__(self):
        return f"{self.post_id} / {self.ip_address} / {self.viewed_on}"


class PostLike(models.Model):
    post = models.ForeignKey(
        Post,
        related_name="likes",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="liked_travel_posts",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "루트 추천"
        verbose_name_plural = "루트 추천"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                condition=Q(user__isnull=False),
                name="unique_post_like_per_user",
            ),
            models.UniqueConstraint(
                fields=["post", "ip_address"],
                condition=Q(user__isnull=True, ip_address__isnull=False),
                name="unique_post_like_per_ip_guest",
            ),
        ]
        indexes = [
            models.Index(fields=["post"]),
            models.Index(fields=["user"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        if self.user_id:
            return f"{self.post_id} / user {self.user_id}"

        return f"{self.post_id} / ip {self.ip_address}"


class PostReview(models.Model):
    post = models.ForeignKey(
        Post,
        related_name="reviews",
        on_delete=models.CASCADE,
        verbose_name="여행 루트",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="route_reviews",
        verbose_name="작성자",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
        verbose_name="별점",
    )

    comment = models.TextField(
        blank=True,
        default="",
        verbose_name="리뷰 내용",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="노출 여부",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="작성일",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "루트 리뷰"
        verbose_name_plural = "루트 리뷰"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="unique_route_review_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["post", "is_active"]),
            models.Index(fields=["user"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.post_id} / {self.user_id} / {self.rating}점"

    @property
    def author_nickname(self):
        profile = getattr(self.user, "profile", None)

        if profile and profile.nickname:
            return profile.nickname

        if self.user.username:
            return self.user.username

        if self.user.email:
            return self.user.email.split("@")[0]

        return f"user{self.user_id}"

    @property
    def rating_percent(self):
        return min(100, max(0, int((self.rating / 5) * 100)))
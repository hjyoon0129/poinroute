from django.conf import settings
from django.db import models
from django.utils import timezone


class CommunityPost(models.Model):
    class Category(models.TextChoices):
        FREE = "free", "자유게시판"
        QUESTION = "question", "여행 질문"
        TIP = "tip", "여행 꿀팁"
        COMPANION = "companion", "동행 구하기"
        NOTICE = "notice", "공지사항"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
        verbose_name="작성자",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.FREE,
        verbose_name="카테고리",
    )

    title = models.CharField(
        max_length=120,
        verbose_name="제목",
    )

    content = models.TextField(
        verbose_name="내용",
    )

    image = models.ImageField(
        upload_to="community/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="이미지",
    )

    views = models.PositiveIntegerField(
        default=0,
        verbose_name="조회수",
    )

    is_notice = models.BooleanField(
        default=False,
        verbose_name="공지 고정",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="노출 여부",
    )

    bumped_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="끌어올린 시간",
        help_text="포인트를 사용해 게시글을 최신 영역으로 끌어올린 시간입니다. 별도 표시 효과는 없습니다.",
    )

    hot_until = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="핫라인 노출 종료",
        help_text="이 시간까지 핫라인 상위 노출됩니다.",
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
        verbose_name = "커뮤니티 글"
        verbose_name_plural = "커뮤니티 글"
        ordering = ["-is_notice", "-hot_until", "-bumped_at", "-created_at"]
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["is_notice", "-created_at"]),
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["views", "-created_at"]),
            models.Index(fields=["hot_until", "-created_at"]),
            models.Index(fields=["bumped_at", "-created_at"]),
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
    def comment_count(self):
        return self.comments.filter(is_active=True).count()

    @property
    def active_likes_count(self):
        return self.likes.filter(is_active=True).count()

    @property
    def is_hot_now(self):
        if not self.hot_until:
            return False
        return self.hot_until > timezone.now()


class CommunityComment(models.Model):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="게시글",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comments",
        verbose_name="작성자",
    )

    content = models.TextField(
        verbose_name="댓글 내용",
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
        verbose_name = "커뮤니티 댓글"
        verbose_name_plural = "커뮤니티 댓글"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "is_active", "created_at"]),
        ]

    def __str__(self):
        return f"{self.post.title} - {self.author_nickname}"

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


class CommunityPostView(models.Model):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="view_logs",
        verbose_name="게시글",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="community_view_logs",
        verbose_name="사용자",
    )

    ip_address = models.GenericIPAddressField(
        verbose_name="IP 주소",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="조회일",
    )

    class Meta:
        verbose_name = "커뮤니티 조회 기록"
        verbose_name_plural = "커뮤니티 조회 기록"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "ip_address"],
                name="unique_community_post_view_per_ip",
            )
        ]
        indexes = [
            models.Index(fields=["post", "ip_address"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.post_id} - {self.ip_address}"


class CommunityPostLike(models.Model):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="게시글",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_likes",
        verbose_name="사용자",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="좋아요 유지",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="처음 누른 날짜",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="수정일",
    )

    class Meta:
        verbose_name = "커뮤니티 좋아요"
        verbose_name_plural = "커뮤니티 좋아요"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="unique_community_post_like_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["post", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.post_id} - {self.user_id} - {self.is_active}"
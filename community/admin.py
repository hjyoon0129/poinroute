from django.contrib import admin

from .models import (
    CommunityPost,
    CommunityComment,
    CommunityPostView,
    CommunityPostLike,
)


class CommunityCommentInline(admin.TabularInline):
    model = CommunityComment
    extra = 0
    fields = (
        "author",
        "content",
        "is_active",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author_display",
        "category",
        "is_notice",
        "is_active",
        "views",
        "like_count_display",
        "comment_count_display",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_notice",
        "is_active",
        "created_at",
    )

    search_fields = (
        "title",
        "content",
        "author__username",
        "author__email",
        "author__profile__nickname",
    )

    readonly_fields = (
        "views",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "기본 정보",
            {
                "fields": (
                    "author",
                    "category",
                    "title",
                    "content",
                    "image",
                )
            },
        ),
        (
            "운영 설정",
            {
                "fields": (
                    "is_notice",
                    "is_active",
                )
            },
        ),
        (
            "통계",
            {
                "fields": (
                    "views",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = [CommunityCommentInline]

    @admin.display(description="작성자")
    def author_display(self, obj):
        return obj.author_nickname

    @admin.display(description="댓글수")
    def comment_count_display(self, obj):
        return obj.comments.filter(is_active=True).count()

    @admin.display(description="추천수")
    def like_count_display(self, obj):
        return obj.likes.filter(is_active=True).count()


@admin.register(CommunityComment)
class CommunityCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "author_display",
        "short_content",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "content",
        "post__title",
        "author__username",
        "author__email",
        "author__profile__nickname",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    @admin.display(description="작성자")
    def author_display(self, obj):
        return obj.author_nickname

    @admin.display(description="내용")
    def short_content(self, obj):
        if len(obj.content) > 40:
            return obj.content[:40] + "..."
        return obj.content


@admin.register(CommunityPostView)
class CommunityPostViewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "user",
        "ip_address",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "post__title",
        "user__username",
        "user__email",
        "user__profile__nickname",
        "ip_address",
    )

    readonly_fields = (
        "post",
        "user",
        "ip_address",
        "created_at",
    )


@admin.register(CommunityPostLike)
class CommunityPostLikeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "user",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_active",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "post__title",
        "user__username",
        "user__email",
        "user__profile__nickname",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )
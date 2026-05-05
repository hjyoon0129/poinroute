from .models import Post


def review_notice(request):
    if not request.user.is_authenticated:
        return {
            "review_notice_post": None,
        }

    notice_post = (
        Post.objects
        .filter(
            author=request.user,
            review_notice_read=False,
            review_status__in=[
                Post.ReviewStatus.APPROVED,
                Post.ReviewStatus.NEEDS_EDIT,
                Post.ReviewStatus.REJECTED,
            ],
        )
        .select_related("author", "author__profile", "reviewed_by")
        .order_by("-reviewed_at", "-updated_at")
        .first()
    )

    return {
        "review_notice_post": notice_post,
    }

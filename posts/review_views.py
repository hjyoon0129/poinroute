from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Post, PostReview


@login_required
@require_POST
def create_or_update_review(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if post.author_id == request.user.id:
        messages.error(request, "본인이 작성한 루트에는 별점 리뷰를 남길 수 없습니다.")
        return redirect("posts:detail", pk=post.pk)

    rating_raw = request.POST.get("rating", "")
    comment = request.POST.get("comment", "").strip()

    try:
        rating = int(rating_raw)
    except ValueError:
        messages.error(request, "별점을 선택해주세요.")
        return redirect("posts:detail", pk=post.pk)

    if rating < 1 or rating > 5:
        messages.error(request, "별점은 1점부터 5점까지만 선택할 수 있습니다.")
        return redirect("posts:detail", pk=post.pk)

    review, created = PostReview.objects.update_or_create(
        post=post,
        user=request.user,
        defaults={
            "rating": rating,
            "comment": comment,
            "is_active": True,
        },
    )

    if created:
        messages.success(request, "리뷰가 등록되었습니다.")
    else:
        messages.success(request, "리뷰가 수정되었습니다.")

    return redirect("posts:detail", pk=post.pk)
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, IntegerField, ExpressionWrapper, Case, When, Value
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommunityPostForm, CommunityCommentForm
from .models import (
    CommunityPost,
    CommunityComment,
    CommunityPostView,
    CommunityPostLike,
)


BUMP_POST_COST = 50
HOTLINE_POST_COST = 200
HOTLINE_DAYS = 7


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _get_profile_for_update(user):
    try:
        profile = user.profile
    except Exception:
        return None

    profile_model = profile.__class__
    return profile_model.objects.select_for_update().get(pk=profile.pk)


def _spend_user_points(user, amount):
    profile = _get_profile_for_update(user)

    if not profile:
        return False, "프로필 정보를 찾을 수 없습니다."

    current_points = getattr(profile, "points", 0) or 0

    if current_points < amount:
        return False, f"포인트가 부족합니다. 필요 포인트: {amount}P"

    profile.points = current_points - amount
    profile.save(update_fields=["points"])

    return True, ""


def community_list(request):
    category = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "latest").strip()
    now = timezone.now()

    allowed_sorts = {
        "latest": "최신순",
        "popular": "인기순",
        "views": "조회순",
        "likes": "추천순",
    }

    if sort not in allowed_sorts:
        sort = "latest"

    posts = (
        CommunityPost.objects
        .filter(is_active=True)
        .select_related("author", "author__profile")
        .annotate(
            active_comment_count=Count(
                "comments",
                filter=Q(comments__is_active=True),
                distinct=True,
            ),
            active_like_count=Count(
                "likes",
                filter=Q(likes__is_active=True),
                distinct=True,
            ),
            hot_priority=Case(
                When(hot_until__gt=now, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .annotate(
            popularity_score=ExpressionWrapper(
                F("active_like_count") * 5
                + F("active_comment_count") * 2
                + F("views"),
                output_field=IntegerField(),
            )
        )
    )

    if category:
        posts = posts.filter(category=category)

    if query:
        posts = posts.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(author__username__icontains=query)
            | Q(author__email__icontains=query)
            | Q(author__profile__nickname__icontains=query)
        )

    if sort == "popular":
        posts = posts.order_by(
            "-is_notice",
            "-hot_priority",
            "-popularity_score",
            "-bumped_at",
            "-created_at",
        )
    elif sort == "views":
        posts = posts.order_by(
            "-is_notice",
            "-hot_priority",
            "-views",
            "-bumped_at",
            "-created_at",
        )
    elif sort == "likes":
        posts = posts.order_by(
            "-is_notice",
            "-hot_priority",
            "-active_like_count",
            "-bumped_at",
            "-created_at",
        )
    else:
        posts = posts.order_by(
            "-is_notice",
            "-hot_priority",
            "-bumped_at",
            "-created_at",
        )

    paginator = Paginator(posts, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "category": category,
        "query": query,
        "sort": sort,
        "category_choices": CommunityPost.Category.choices,
        "sort_choices": allowed_sorts.items(),
    }

    return render(request, "community/community_list.html", context)


def community_detail(request, pk):
    post = get_object_or_404(
        CommunityPost.objects.select_related("author", "author__profile"),
        pk=pk,
        is_active=True,
    )

    ip_address = get_client_ip(request)
    view_user = request.user if request.user.is_authenticated else None

    view_log, created = CommunityPostView.objects.get_or_create(
        post=post,
        ip_address=ip_address,
        defaults={
            "user": view_user,
        },
    )

    if created:
        CommunityPost.objects.filter(pk=post.pk).update(views=F("views") + 1)
        post.refresh_from_db(fields=["views"])
    else:
        if view_user and view_log.user_id is None:
            view_log.user = view_user
            view_log.save(update_fields=["user"])

    comments = (
        post.comments
        .filter(is_active=True)
        .select_related("author", "author__profile")
        .order_by("created_at")
    )

    active_like_count = post.likes.filter(is_active=True).count()

    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = post.likes.filter(
            user=request.user,
            is_active=True,
        ).exists()

    comment_form = CommunityCommentForm()

    context = {
        "post": post,
        "comments": comments,
        "comment_form": comment_form,
        "active_like_count": active_like_count,
        "user_has_liked": user_has_liked,
        "bump_post_cost": BUMP_POST_COST,
        "hotline_post_cost": HOTLINE_POST_COST,
        "hotline_days": HOTLINE_DAYS,
    }

    return render(request, "community/community_detail.html", context)


@login_required
def community_create(request):
    if request.method == "POST":
        form = CommunityPostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user

            if post.category == CommunityPost.Category.NOTICE and not request.user.is_staff:
                post.category = CommunityPost.Category.FREE
                post.is_notice = False

            post.save()

            messages.success(request, "커뮤니티 글이 등록되었습니다.")
            return redirect("community:detail", pk=post.pk)
    else:
        form = CommunityPostForm()

    context = {
        "form": form,
        "form_title": "커뮤니티 글쓰기",
        "submit_label": "등록하기",
    }

    return render(request, "community/community_form.html", context)


@login_required
def community_update(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "수정 권한이 없습니다.")
        return redirect("community:detail", pk=post.pk)

    if request.method == "POST":
        form = CommunityPostForm(request.POST, request.FILES, instance=post)

        if form.is_valid():
            updated_post = form.save(commit=False)

            if updated_post.category == CommunityPost.Category.NOTICE and not request.user.is_staff:
                updated_post.category = CommunityPost.Category.FREE
                updated_post.is_notice = False

            updated_post.save()

            messages.success(request, "커뮤니티 글이 수정되었습니다.")
            return redirect("community:detail", pk=post.pk)
    else:
        form = CommunityPostForm(instance=post)

    context = {
        "form": form,
        "post": post,
        "form_title": "커뮤니티 글 수정",
        "submit_label": "수정하기",
    }

    return render(request, "community/community_form.html", context)


@login_required
@require_POST
def community_delete(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "삭제 권한이 없습니다.")
        return redirect("community:detail", pk=post.pk)

    post.is_active = False
    post.save(update_fields=["is_active"])

    messages.success(request, "커뮤니티 글이 삭제되었습니다.")
    return redirect("community:list")


@login_required
@require_POST
def community_like_toggle(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    like, created = CommunityPostLike.objects.get_or_create(
        post=post,
        user=request.user,
        defaults={
            "is_active": True,
        },
    )

    if created:
        messages.success(request, "추천했습니다.")
    else:
        like.is_active = not like.is_active
        like.save(update_fields=["is_active", "updated_at"])

        if like.is_active:
            messages.success(request, "추천했습니다.")
        else:
            messages.info(request, "추천을 취소했습니다.")

    return redirect("community:detail", pk=post.pk)


@login_required
@require_POST
def community_bump_post(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "끌어올리기 권한이 없습니다.")
        return redirect("community:detail", pk=post.pk)

    with transaction.atomic():
        locked_post = CommunityPost.objects.select_for_update().get(pk=post.pk)
        ok, error_message = _spend_user_points(request.user, BUMP_POST_COST)

        if not ok:
            messages.error(request, error_message)
            return redirect("community:detail", pk=post.pk)

        locked_post.bumped_at = timezone.now()
        locked_post.save(update_fields=["bumped_at"])

    messages.success(request, f"{BUMP_POST_COST}P를 사용해 게시글을 상단으로 끌어올렸습니다.")
    return redirect("community:detail", pk=post.pk)


@login_required
@require_POST
def community_hotline_post(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    if post.author != request.user and not request.user.is_staff:
        messages.error(request, "핫라인 등록 권한이 없습니다.")
        return redirect("community:detail", pk=post.pk)

    now = timezone.now()

    with transaction.atomic():
        locked_post = CommunityPost.objects.select_for_update().get(pk=post.pk)
        ok, error_message = _spend_user_points(request.user, HOTLINE_POST_COST)

        if not ok:
            messages.error(request, error_message)
            return redirect("community:detail", pk=post.pk)

        locked_post.hot_until = now + timedelta(days=HOTLINE_DAYS)
        locked_post.bumped_at = now
        locked_post.save(update_fields=["hot_until", "bumped_at"])

    messages.success(
        request,
        f"{HOTLINE_POST_COST}P를 사용해 {HOTLINE_DAYS}일간 핫라인에 등록했습니다.",
    )
    return redirect("community:detail", pk=post.pk)


@login_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(
        CommunityPost,
        pk=pk,
        is_active=True,
    )

    form = CommunityCommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()

        messages.success(request, "댓글이 등록되었습니다.")
    else:
        messages.error(request, "댓글 내용을 확인해주세요.")

    return redirect("community:detail", pk=post.pk)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(
        CommunityComment.objects.select_related("post"),
        pk=pk,
        is_active=True,
    )

    post = comment.post

    if comment.author != request.user and not request.user.is_staff:
        messages.error(request, "댓글 삭제 권한이 없습니다.")
        return redirect("community:detail", pk=post.pk)

    comment.is_active = False
    comment.save(update_fields=["is_active"])

    messages.success(request, "댓글이 삭제되었습니다.")
    return redirect("community:detail", pk=post.pk)
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PlaceFormSet, PostForm
from .models import Post, PostLike, PostView


def _visit_time_sort_value(value):
    if not value:
        return 9999

    text = str(value).strip()
    period = None

    if "오전" in text:
        period = "AM"
        text = text.replace("오전", "").strip()
    elif "오후" in text:
        period = "PM"
        text = text.replace("오후", "").strip()

    try:
        hour_text, minute_text = text.split(":")
        hour = int(hour_text)
        minute = int(minute_text)
    except Exception:
        return 9999

    if period == "AM":
        if hour == 12:
            hour = 0
    elif period == "PM":
        if hour != 12:
            hour += 12

    return hour * 60 + minute


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "").strip()

    return ip or "0.0.0.0"


def _to_positive_int(value):
    if value in (None, ""):
        return None

    try:
        number = int(str(value).replace(",", "").strip())
    except ValueError:
        return None

    if number < 0:
        return None

    return number


def _extract_number_from_keyword(keyword):
    if not keyword:
        return None

    match = re.search(r"\d+", keyword.replace(",", ""))

    if not match:
        return None

    return _to_positive_int(match.group(0))


def _can_edit_post(user, post):
    if not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    return post.author_id == user.id


def _can_view_post(user, post):
    if post.review_status == Post.ReviewStatus.APPROVED:
        return True

    if not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    return post.author_id == user.id


def _increment_post_views_once_per_ip_day(request, post):
    ip_address = _get_client_ip(request)
    today = timezone.localdate()

    try:
        _, created = PostView.objects.get_or_create(
            post=post,
            ip_address=ip_address,
            viewed_on=today,
        )
    except IntegrityError:
        created = False

    if created:
        Post.objects.filter(pk=post.pk).update(views=F("views") + 1)
        post.refresh_from_db(fields=["views"])


def _liked_by_current_visitor(request, post):
    ip_address = _get_client_ip(request)

    if request.user.is_authenticated:
        return PostLike.objects.filter(post=post, user=request.user).exists()

    return PostLike.objects.filter(
        post=post,
        user__isnull=True,
        ip_address=ip_address,
    ).exists()


def post_list(request):
    search_reg = request.GET.get("start_region", "").strip()
    search_dist = request.GET.get("start_district", "").strip()
    search_neigh = request.GET.get("start_neighborhood", "").strip()
    search_keyword = request.GET.get("dest_loc", "").strip()
    search_theme = request.GET.get("theme", "").strip()
    selected_sort = request.GET.get("sort", "latest").strip()

    min_likes = _to_positive_int(request.GET.get("min_likes", ""))
    min_views = _to_positive_int(request.GET.get("min_views", ""))

    theme_choices = [
        (str(value), label)
        for value, label in Post._meta.get_field("theme").choices
    ]

    posts = (
        Post.objects
        .select_related("author", "author__profile")
        .prefetch_related("places")
        .annotate(likes_total=Count("likes", distinct=True))
    )

    if request.user.is_authenticated:
        if not request.user.is_staff and not request.user.is_superuser:
            posts = posts.filter(
                Q(review_status=Post.ReviewStatus.APPROVED) |
                Q(author=request.user)
            )
    else:
        posts = posts.filter(review_status=Post.ReviewStatus.APPROVED)

    if search_reg:
        posts = posts.filter(start_region=search_reg)

    if search_dist:
        posts = posts.filter(start_district=search_dist)

    if search_neigh:
        posts = posts.filter(start_neighborhood=search_neigh)

    if search_theme:
        posts = posts.filter(theme=search_theme)

    if min_likes is not None:
        posts = posts.filter(likes_total__gte=min_likes)

    if min_views is not None:
        posts = posts.filter(views__gte=min_views)

    if search_keyword:
        keyword = search_keyword
        number_keyword = _extract_number_from_keyword(keyword)

        search_query = (
            Q(destination__icontains=keyword) |
            Q(title__icontains=keyword) |
            Q(start_region__icontains=keyword) |
            Q(start_district__icontains=keyword) |
            Q(start_neighborhood__icontains=keyword) |
            Q(start_place_name__icontains=keyword) |
            Q(places__place_name__icontains=keyword) |
            Q(places__description__icontains=keyword) |
            Q(author__profile__nickname__icontains=keyword) |
            Q(author__username__icontains=keyword)
        )

        if number_keyword is not None:
            search_query = (
                search_query |
                Q(views__gte=number_keyword) |
                Q(likes_total__gte=number_keyword)
            )

        posts = posts.filter(search_query).distinct()

    if selected_sort == "likes":
        posts = posts.order_by("-likes_total", "-views", "-created_at")
    elif selected_sort == "views":
        posts = posts.order_by("-views", "-likes_total", "-created_at")
    elif selected_sort == "popular":
        posts = posts.order_by("-likes_total", "-views", "-created_at")
    else:
        selected_sort = "latest"
        posts = posts.order_by("-created_at")

    return render(request, "posts/post_list.html", {
        "posts": posts,
        "theme_choices": theme_choices,
        "selected_theme": search_theme,
        "selected_sort": selected_sort,
        "search_keyword": search_keyword,
        "selected_min_likes": "" if min_likes is None else min_likes,
        "selected_min_views": "" if min_views is None else min_views,
    })


def post_detail(request, pk):
    post = get_object_or_404(
        Post.objects
        .select_related("author", "author__profile")
        .annotate(likes_total=Count("likes", distinct=True)),
        pk=pk,
    )

    if not _can_view_post(request.user, post):
        raise PermissionDenied("아직 공개되지 않은 루트입니다.")

    _increment_post_views_once_per_ip_day(request, post)

    ordered_places = sorted(
        list(post.places.all()),
        key=lambda place: (
            place.day or 1,
            _visit_time_sort_value(place.visit_time_str),
            place.id or 0,
        )
    )

    days_data = {}

    for place in ordered_places:
        day = place.day or 1

        if day not in days_data:
            days_data[day] = {
                "day": day,
                "places": [],
                "daily_cost": 0,
            }

        days_data[day]["places"].append(place)
        days_data[day]["daily_cost"] += place.cost or 0

    grouped_places = sorted(days_data.values(), key=lambda x: x["day"])

    return render(request, "posts/post_detail.html", {
        "post": post,
        "ordered_places": ordered_places,
        "grouped_places": grouped_places,
        "can_edit_post": _can_edit_post(request.user, post),
        "liked_by_current_visitor": _liked_by_current_visitor(request, post),
    })


@require_POST
def post_like(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if post.review_status != Post.ReviewStatus.APPROVED:
        messages.error(request, "아직 승인되지 않은 루트는 추천할 수 없습니다.")
        return redirect("posts:detail", pk=post.pk)

    ip_address = _get_client_ip(request)

    try:
        if request.user.is_authenticated:
            _, created = PostLike.objects.get_or_create(
                post=post,
                user=request.user,
                defaults={"ip_address": ip_address},
            )
        else:
            _, created = PostLike.objects.get_or_create(
                post=post,
                user=None,
                ip_address=ip_address,
            )
    except IntegrityError:
        created = False

    if created:
        messages.success(request, "이 루트를 추천했어요.")
    else:
        messages.info(request, "이미 추천한 루트입니다.")

    return redirect("posts:detail", pk=post.pk)


def _update_post_total_cost(post):
    total_cost = post.places.aggregate(total=Sum("cost"))["total"] or 0
    post.total_cost = total_cost
    post.save(update_fields=["total_cost"])


def _get_update_place_formset_class(extra=0):
    return type(
        "PlaceUpdateFormSet",
        (PlaceFormSet,),
        {
            "extra": extra,
            "min_num": 0,
            "validate_min": False,
        },
    )


def _is_empty_place_form(place_form):
    cleaned_data = getattr(place_form, "cleaned_data", None)

    if not cleaned_data:
        return True

    place_name = cleaned_data.get("place_name")
    description = cleaned_data.get("description")
    image = cleaned_data.get("image")
    visit_time_str = cleaned_data.get("visit_time_str")
    latitude = cleaned_data.get("latitude")
    longitude = cleaned_data.get("longitude")
    cost = cleaned_data.get("cost") or 0

    return not any([
        place_name,
        description,
        image,
        visit_time_str,
        latitude,
        longitude,
        cost,
    ])


def _mark_empty_place_forms_as_delete(post_data, prefix="places"):
    mutable_data = post_data.copy()

    total_forms_key = f"{prefix}-TOTAL_FORMS"
    total_forms = int(mutable_data.get(total_forms_key, 0) or 0)

    for index in range(total_forms):
        form_prefix = f"{prefix}-{index}"

        place_id = mutable_data.get(f"{form_prefix}-id", "").strip()
        place_name = mutable_data.get(f"{form_prefix}-place_name", "").strip()
        description = mutable_data.get(f"{form_prefix}-description", "").strip()
        visit_time_str = mutable_data.get(f"{form_prefix}-visit_time_str", "").strip()
        latitude = mutable_data.get(f"{form_prefix}-latitude", "").strip()
        longitude = mutable_data.get(f"{form_prefix}-longitude", "").strip()
        cost = mutable_data.get(f"{form_prefix}-cost", "").strip()

        try:
            has_cost = int(cost or 0) > 0
        except ValueError:
            has_cost = False

        is_empty_card = not any([
            place_name,
            description,
            visit_time_str,
            latitude,
            longitude,
            has_cost,
        ])

        if place_id and is_empty_card:
            mutable_data[f"{form_prefix}-DELETE"] = "on"

    return mutable_data


def _save_place_formset(post, formset):
    for place_form in formset.forms:
        cleaned_data = getattr(place_form, "cleaned_data", None)

        if not cleaned_data:
            continue

        should_delete = cleaned_data.get("DELETE", False)

        if should_delete:
            if place_form.instance and place_form.instance.pk:
                place_form.instance.delete()
            continue

        if not place_form.instance.pk and _is_empty_place_form(place_form):
            continue

        if place_form.instance.pk and _is_empty_place_form(place_form):
            place_form.instance.delete()
            continue

        place = place_form.save(commit=False)
        place.post = post
        place.save()

    if hasattr(formset, "save_m2m"):
        formset.save_m2m()


@login_required(login_url="/auth/login/")
def post_create(request):
    profile = getattr(request.user, "profile", None)

    if profile and not profile.nickname:
        messages.info(request, "루트를 등록하기 전에 닉네임을 먼저 설정해주세요.")
        return redirect("posts:list")

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        formset = PlaceFormSet(request.POST, request.FILES)

        if form.is_valid() and formset.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.review_status = Post.ReviewStatus.PENDING
            post.review_notice_read = True
            post.points_awarded = False
            post.awarded_points = 0
            post.review_note = ""
            post.reviewed_by = None
            post.reviewed_at = None
            post.save()

            formset.instance = post
            _save_place_formset(post, formset)
            _update_post_total_cost(post)

            messages.success(request, "루트가 등록되었습니다. 검수 후 포인트 지급 여부가 안내됩니다.")
            return redirect("posts:detail", pk=post.pk)

    else:
        form = PostForm()
        formset = PlaceFormSet()

    return render(request, "posts/post_form.html", {
        "form": form,
        "formset": formset,
        "is_update": False,
    })


@login_required(login_url="/auth/login/")
def post_update(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if not _can_edit_post(request.user, post):
        raise PermissionDenied("이 루트를 수정할 권한이 없습니다.")

    update_extra = 0 if post.places.exists() else 1
    PlaceUpdateFormSet = _get_update_place_formset_class(extra=update_extra)

    if request.method == "POST":
        post_data = _mark_empty_place_forms_as_delete(request.POST, prefix="places")

        form = PostForm(post_data, request.FILES, instance=post)
        formset = PlaceUpdateFormSet(post_data, request.FILES, instance=post)

        if form.is_valid() and formset.is_valid():
            post = form.save(commit=False)

            if not request.user.is_staff and not request.user.is_superuser:
                post.review_status = Post.ReviewStatus.PENDING
                post.review_notice_read = True
                post.review_note = ""
                post.reviewed_by = None
                post.reviewed_at = None

            post.save()

            formset.instance = post
            _save_place_formset(post, formset)
            _update_post_total_cost(post)

            messages.success(request, "루트가 수정되었습니다. 수정된 내용은 다시 검수됩니다.")
            return redirect("posts:detail", pk=post.pk)

    else:
        form = PostForm(instance=post)
        formset = PlaceUpdateFormSet(instance=post)

    return render(request, "posts/post_form.html", {
        "form": form,
        "formset": formset,
        "is_update": True,
    })


@login_required(login_url="/auth/login/")
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if not _can_edit_post(request.user, post):
        raise PermissionDenied("이 루트를 삭제할 권한이 없습니다.")

    if request.method == "POST":
        post.delete()
        return redirect("posts:list")

    return redirect("posts:detail", pk=pk)


@login_required(login_url="/auth/login/")
@require_POST
def read_review_notice(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)

    post.review_notice_read = True
    post.save(update_fields=["review_notice_read"])

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)

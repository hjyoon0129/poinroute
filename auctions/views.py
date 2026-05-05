from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AuctionRequestForm, AuctionAnswerForm
from .models import AuctionRequest, AuctionAnswer


def get_user_nickname(user):
    try:
        if user.profile.nickname:
            return user.profile.nickname
    except Exception:
        pass

    if user.username:
        return user.username

    if user.email:
        return user.email

    return "여행자"


def get_profile_for_update(user):
    try:
        profile = user.profile
    except Exception:
        return None

    profile_model = profile.__class__
    return profile_model.objects.select_for_update().get(pk=profile.pk)


def spend_user_points(user, amount):
    profile = get_profile_for_update(user)

    if not profile:
        return False, "프로필 정보를 찾을 수 없습니다."

    current_points = getattr(profile, "points", 0) or 0

    if current_points < amount:
        return False, f"포인트가 부족합니다. 필요 포인트: {amount}P"

    profile.points = current_points - amount
    profile.save(update_fields=["points"])

    return True, ""


def add_user_points(user, amount):
    profile = get_profile_for_update(user)

    if not profile:
        return False, "프로필 정보를 찾을 수 없습니다."

    current_points = getattr(profile, "points", 0) or 0
    profile.points = current_points + amount

    update_fields = ["points"]

    if hasattr(profile, "total_earned_points"):
        current_total_earned = getattr(profile, "total_earned_points", 0) or 0
        profile.total_earned_points = current_total_earned + amount
        update_fields.append("total_earned_points")

    profile.save(update_fields=update_fields)

    return True, ""


def auction_list(request):
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "latest").strip()
    query = request.GET.get("q", "").strip()

    allowed_sorts = {
        "latest": "최신순",
        "reward": "보상 높은 순",
        "deadline": "마감 임박",
        "answers": "답변 많은 순",
    }

    if sort not in allowed_sorts:
        sort = "latest"

    auction_requests = (
        AuctionRequest.objects
        .filter(is_active=True)
        .select_related("author", "author__profile")
        .annotate(
            answer_count_for_sort=Count(
                "answers",
                filter=Q(answers__is_active=True),
                distinct=True,
            )
        )
    )

    if status:
        auction_requests = auction_requests.filter(status=status)

    if query:
        auction_requests = auction_requests.filter(
            Q(title__icontains=query)
            | Q(destination__icontains=query)
            | Q(start_area__icontains=query)
            | Q(request_detail__icontains=query)
            | Q(author__username__icontains=query)
            | Q(author__email__icontains=query)
            | Q(author__profile__nickname__icontains=query)
        )

    if sort == "reward":
        auction_requests = auction_requests.order_by("-reward_points", "-created_at")
    elif sort == "deadline":
        auction_requests = auction_requests.order_by("deadline_at", "-created_at")
    elif sort == "answers":
        auction_requests = auction_requests.order_by("-answer_count_for_sort", "-created_at")
    else:
        auction_requests = auction_requests.order_by("-created_at")

    paginator = Paginator(auction_requests, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "status": status,
        "sort": sort,
        "query": query,
        "status_choices": AuctionRequest.Status.choices,
        "sort_choices": allowed_sorts.items(),
    }

    return render(request, "auctions/auction_list.html", context)


@login_required
def auction_create(request):
    if request.method == "POST":
        form = AuctionRequestForm(request.POST)

        if form.is_valid():
            reward_points = form.cleaned_data["reward_points"]

            with transaction.atomic():
                ok, error_message = spend_user_points(request.user, reward_points)

                if not ok:
                    form.add_error("reward_points", error_message)
                else:
                    auction_request = form.save(commit=False)
                    auction_request.author = request.user
                    auction_request.status = AuctionRequest.Status.OPEN
                    auction_request.save()

                    messages.success(
                        request,
                        f"{reward_points}P를 예치하고 루트 의뢰를 등록했습니다.",
                    )
                    return redirect("auctions:detail", pk=auction_request.pk)
    else:
        form = AuctionRequestForm()

    context = {
        "form": form,
        "title": "루트 의뢰 등록",
        "submit_label": "포인트 걸고 의뢰 등록",
    }

    return render(request, "auctions/auction_form.html", context)


def auction_detail(request, pk):
    auction_request = get_object_or_404(
        AuctionRequest.objects.select_related(
            "author",
            "author__profile",
            "selected_answer",
        ),
        pk=pk,
        is_active=True,
    )

    answers = (
        auction_request.answers
        .filter(is_active=True)
        .select_related("author", "author__profile")
        .order_by("-is_selected", "created_at")
    )

    can_answer = False
    if request.user.is_authenticated:
        can_answer = (
            auction_request.can_receive_answers
            and auction_request.author_id != request.user.id
        )

    can_select = False
    if request.user.is_authenticated:
        can_select = (
            auction_request.status == AuctionRequest.Status.OPEN
            and auction_request.author_id == request.user.id
        )

    can_cancel = False
    if request.user.is_authenticated:
        can_cancel = (
            auction_request.status == AuctionRequest.Status.OPEN
            and auction_request.author_id == request.user.id
            and not answers.exists()
        )

    context = {
        "auction": auction_request,
        "answers": answers,
        "can_answer": can_answer,
        "can_select": can_select,
        "can_cancel": can_cancel,
    }

    return render(request, "auctions/auction_detail.html", context)


@login_required
def answer_create(request, pk):
    auction_request = get_object_or_404(
        AuctionRequest,
        pk=pk,
        is_active=True,
    )

    if not auction_request.can_receive_answers:
        messages.error(request, "현재 답변을 작성할 수 없는 의뢰입니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    if auction_request.author_id == request.user.id:
        messages.error(request, "본인이 작성한 의뢰에는 답변할 수 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    already_answered = auction_request.answers.filter(
        author=request.user,
        is_active=True,
    ).exists()

    if already_answered:
        messages.error(request, "이미 이 의뢰에 답변을 작성했습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    if request.method == "POST":
        form = AuctionAnswerForm(request.POST)

        if form.is_valid():
            answer = form.save(commit=False)
            answer.request = auction_request
            answer.author = request.user
            answer.save()

            messages.success(request, "코스 답변이 등록되었습니다.")
            return redirect("auctions:detail", pk=auction_request.pk)
    else:
        form = AuctionAnswerForm()

    context = {
        "form": form,
        "auction": auction_request,
        "title": "코스 답변 작성",
        "submit_label": "답변 등록",
    }

    return render(request, "auctions/answer_form.html", context)


@login_required
@require_POST
def select_answer(request, pk, answer_pk):
    auction_request = get_object_or_404(
        AuctionRequest,
        pk=pk,
        is_active=True,
    )

    if auction_request.author_id != request.user.id:
        messages.error(request, "답변 채택 권한이 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    if auction_request.status != AuctionRequest.Status.OPEN:
        messages.error(request, "이미 종료된 의뢰입니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    answer = get_object_or_404(
        AuctionAnswer.objects.select_related("author"),
        pk=answer_pk,
        request=auction_request,
        is_active=True,
    )

    if answer.author_id == request.user.id:
        messages.error(request, "본인 답변은 채택할 수 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    with transaction.atomic():
        locked_request = AuctionRequest.objects.select_for_update().get(
            pk=auction_request.pk
        )

        if locked_request.status != AuctionRequest.Status.OPEN:
            messages.error(request, "이미 종료된 의뢰입니다.")
            return redirect("auctions:detail", pk=auction_request.pk)

        locked_answer = AuctionAnswer.objects.select_for_update().get(pk=answer.pk)

        ok, error_message = add_user_points(
            locked_answer.author,
            locked_request.reward_points,
        )

        if not ok:
            messages.error(request, error_message)
            return redirect("auctions:detail", pk=auction_request.pk)

        AuctionAnswer.objects.filter(request=locked_request).update(is_selected=False)

        locked_answer.is_selected = True
        locked_answer.save(update_fields=["is_selected"])

        locked_request.status = AuctionRequest.Status.SELECTED
        locked_request.selected_answer = locked_answer
        locked_request.selected_at = timezone.now()
        locked_request.save(
            update_fields=[
                "status",
                "selected_answer",
                "selected_at",
                "updated_at",
            ]
        )

    messages.success(
        request,
        f"{get_user_nickname(answer.author)}님의 답변을 채택하고 "
        f"{auction_request.reward_points}P를 지급했습니다.",
    )
    return redirect("auctions:detail", pk=auction_request.pk)


@login_required
@require_POST
def cancel_request(request, pk):
    auction_request = get_object_or_404(
        AuctionRequest,
        pk=pk,
        is_active=True,
    )

    if auction_request.author_id != request.user.id:
        messages.error(request, "의뢰 취소 권한이 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    if auction_request.status != AuctionRequest.Status.OPEN:
        messages.error(request, "이미 종료된 의뢰는 취소할 수 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    if auction_request.answers.filter(is_active=True).exists():
        messages.error(request, "답변이 달린 의뢰는 바로 취소할 수 없습니다.")
        return redirect("auctions:detail", pk=auction_request.pk)

    with transaction.atomic():
        locked_request = AuctionRequest.objects.select_for_update().get(
            pk=auction_request.pk
        )

        if locked_request.status != AuctionRequest.Status.OPEN:
            messages.error(request, "이미 종료된 의뢰입니다.")
            return redirect("auctions:detail", pk=auction_request.pk)

        ok, error_message = add_user_points(
            request.user,
            locked_request.reward_points,
        )

        if not ok:
            messages.error(request, error_message)
            return redirect("auctions:detail", pk=auction_request.pk)

        locked_request.status = AuctionRequest.Status.REFUNDED
        locked_request.refunded_at = timezone.now()
        locked_request.save(
            update_fields=[
                "status",
                "refunded_at",
                "updated_at",
            ]
        )

    messages.success(
        request,
        f"의뢰를 취소하고 {auction_request.reward_points}P를 환불했습니다.",
    )
    return redirect("auctions:detail", pk=auction_request.pk)
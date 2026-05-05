from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from points.services import award_route_approved_points
from .models import Post, Place, PostLike, PostView


DEFAULT_APPROVAL_POINTS = 50
MAX_ADMIN_AWARD_POINTS = 1_000_000


class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = (
        "day",
        "visit_time_str",
        "place_name",
        "cost",
        "latitude",
        "longitude",
        "image",
    )


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author_display",
        "theme",
        "destination",
        "review_status",
        "review_notice_read",
        "points_awarded",
        "awarded_points",
        "views",
        "like_count",
        "place_count",
        "created_at",
        "reviewed_at",
    )

    list_filter = (
        "review_status",
        "review_notice_read",
        "points_awarded",
        "theme",
        "created_at",
        "reviewed_at",
    )

    search_fields = (
        "title",
        "destination",
        "start_region",
        "start_district",
        "start_place_name",
        "author__username",
        "author__email",
        "author__profile__nickname",
        "places__place_name",
    )

    readonly_fields = (
        "views",
        "points_awarded",
        "awarded_points",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "작성자 / 기본 정보",
            {
                "fields": (
                    "author",
                    "title",
                    "theme",
                    "thumbnail",
                    "destination",
                    "travel_start_date",
                    "travel_end_date",
                    "total_cost",
                    "total_time",
                )
            },
        ),
        (
            "출발 정보",
            {
                "fields": (
                    "start_region",
                    "start_district",
                    "start_neighborhood",
                    "start_time",
                    "start_place_name",
                    "start_latitude",
                    "start_longitude",
                )
            },
        ),
        (
            "검수 / 포인트",
            {
                "fields": (
                    "review_status",
                    "review_note",
                    "review_notice_read",
                    "points_awarded",
                    "awarded_points",
                    "reviewed_by",
                    "reviewed_at",
                ),
                "description": (
                    "검수 메모는 사용자에게 모달로 표시될 수 있습니다. "
                    "승인/수정요청/반려는 목록 액션에서 사유 입력 후 처리하는 것을 추천합니다."
                ),
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

    inlines = [PlaceInline]

    actions = (
        "approve_with_50_points",
        "approve_with_custom_points",
        "approve_with_100_points",
        "approve_with_300_points",
        "approve_with_500_points",
        "mark_needs_edit",
        "reject_posts",
        "reset_to_pending",
        "mark_notice_unread",
        "mark_notice_read",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return queryset.select_related(
            "author",
            "author__profile",
            "reviewed_by",
        ).annotate(
            admin_like_count=Count("likes", distinct=True),
            admin_place_count=Count("places", distinct=True),
        )

    @admin.display(description="작성자")
    def author_display(self, obj):
        return obj.author_nickname

    @admin.display(description="추천수", ordering="admin_like_count")
    def like_count(self, obj):
        return obj.admin_like_count

    @admin.display(description="장소수", ordering="admin_place_count")
    def place_count(self, obj):
        return obj.admin_place_count

    def _get_selected_ids(self, queryset):
        return list(queryset.values_list("pk", flat=True))

    def _render_review_reason_form(
        self,
        request,
        queryset,
        *,
        action_name,
        title,
        description,
        submit_label,
        default_note="",
        require_note=True,
        point_amount=None,
        allow_custom_points=False,
        default_points=DEFAULT_APPROVAL_POINTS,
        tone="blue",
        error_message="",
    ):
        selected_ids = self._get_selected_ids(queryset)

        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "queryset": queryset,
            "selected_ids": selected_ids,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "action_name": action_name,
            "description": description,
            "submit_label": submit_label,
            "default_note": request.POST.get("review_note", default_note),
            "require_note": require_note,
            "point_amount": point_amount,
            "allow_custom_points": allow_custom_points,
            "default_points": request.POST.get("custom_points", default_points),
            "max_admin_award_points": MAX_ADMIN_AWARD_POINTS,
            "tone": tone,
            "error_message": error_message,
            "changelist_url": request.get_full_path(),
        }

        return render(
            request,
            "admin/posts/review_action_reason.html",
            context,
        )

    def _get_review_note_or_render_error(
        self,
        request,
        queryset,
        *,
        action_name,
        title,
        description,
        submit_label,
        default_note="",
        require_note=True,
        point_amount=None,
        allow_custom_points=False,
        default_points=DEFAULT_APPROVAL_POINTS,
        tone="blue",
    ):
        review_note = (request.POST.get("review_note") or "").strip()

        if require_note and not review_note:
            return None, self._render_review_reason_form(
                request,
                queryset,
                action_name=action_name,
                title=title,
                description=description,
                submit_label=submit_label,
                default_note=default_note,
                require_note=require_note,
                point_amount=point_amount,
                allow_custom_points=allow_custom_points,
                default_points=default_points,
                tone=tone,
                error_message="검수 사유를 입력해주세요.",
            )

        if not review_note:
            review_note = default_note

        return review_note, None

    def _get_custom_points_or_render_error(
        self,
        request,
        queryset,
        *,
        action_name,
        title,
        description,
        submit_label,
        default_note="",
        require_note=False,
        tone="green",
    ):
        raw_points = (request.POST.get("custom_points") or "").strip()

        try:
            points = int(raw_points)
        except (TypeError, ValueError):
            return None, self._render_review_reason_form(
                request,
                queryset,
                action_name=action_name,
                title=title,
                description=description,
                submit_label=submit_label,
                default_note=default_note,
                require_note=require_note,
                point_amount=None,
                allow_custom_points=True,
                default_points=raw_points or DEFAULT_APPROVAL_POINTS,
                tone=tone,
                error_message="지급할 포인트는 숫자로 입력해주세요.",
            )

        if points <= 0:
            return None, self._render_review_reason_form(
                request,
                queryset,
                action_name=action_name,
                title=title,
                description=description,
                submit_label=submit_label,
                default_note=default_note,
                require_note=require_note,
                point_amount=None,
                allow_custom_points=True,
                default_points=points,
                tone=tone,
                error_message="지급할 포인트는 1P 이상이어야 합니다.",
            )

        if points > MAX_ADMIN_AWARD_POINTS:
            return None, self._render_review_reason_form(
                request,
                queryset,
                action_name=action_name,
                title=title,
                description=description,
                submit_label=submit_label,
                default_note=default_note,
                require_note=require_note,
                point_amount=None,
                allow_custom_points=True,
                default_points=points,
                tone=tone,
                error_message=f"지급할 포인트는 최대 {MAX_ADMIN_AWARD_POINTS:,}P까지 입력할 수 있습니다.",
            )

        return points, None

    def save_model(self, request, obj, form, change):
        now = timezone.now()

        if change:
            old_obj = Post.objects.filter(pk=obj.pk).first()

            if old_obj:
                status_changed = old_obj.review_status != obj.review_status
                note_changed = old_obj.review_note != obj.review_note

                if obj.review_status in [
                    Post.ReviewStatus.APPROVED,
                    Post.ReviewStatus.NEEDS_EDIT,
                    Post.ReviewStatus.REJECTED,
                ] and (status_changed or note_changed):
                    obj.review_notice_read = False
                    obj.reviewed_by = request.user
                    obj.reviewed_at = now

                if obj.review_status == Post.ReviewStatus.PENDING and status_changed:
                    obj.review_notice_read = True
                    obj.reviewed_by = None
                    obj.reviewed_at = None

        super().save_model(request, obj, form, change)

    @admin.action(description="기본 승인 + 50P 지급")
    def approve_with_50_points(self, request, queryset):
        points = DEFAULT_APPROVAL_POINTS

        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="approve_with_50_points",
                title="기본 승인 사유 입력",
                description=f"선택한 여행 루트를 승인하고 작성자에게 기본 {points}P를 지급합니다.",
                submit_label=f"승인하고 {points}P 지급",
                default_note=f"작성하신 여행 루트가 승인되었습니다. {points}P가 지급되었습니다.",
                require_note=False,
                point_amount=points,
                tone="green",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="approve_with_50_points",
            title="기본 승인 사유 입력",
            description=f"선택한 여행 루트를 승인하고 작성자에게 기본 {points}P를 지급합니다.",
            submit_label=f"승인하고 {points}P 지급",
            default_note=f"작성하신 여행 루트가 승인되었습니다. {points}P가 지급되었습니다.",
            require_note=False,
            point_amount=points,
            tone="green",
        )

        if response:
            return response

        return self._approve_and_award_points(request, queryset, points, review_note)

    @admin.action(description="승인 + 포인트 직접 입력")
    def approve_with_custom_points(self, request, queryset):
        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="approve_with_custom_points",
                title="승인 포인트 직접 입력",
                description=(
                    "선택한 여행 루트를 승인하고 작성자에게 원하는 만큼 포인트를 지급합니다. "
                    f"기본값은 {DEFAULT_APPROVAL_POINTS}P입니다."
                ),
                submit_label="승인하고 입력 포인트 지급",
                default_note="",
                require_note=False,
                point_amount=None,
                allow_custom_points=True,
                default_points=DEFAULT_APPROVAL_POINTS,
                tone="green",
            )

        points, response = self._get_custom_points_or_render_error(
            request,
            queryset,
            action_name="approve_with_custom_points",
            title="승인 포인트 직접 입력",
            description=(
                "선택한 여행 루트를 승인하고 작성자에게 원하는 만큼 포인트를 지급합니다. "
                f"기본값은 {DEFAULT_APPROVAL_POINTS}P입니다."
            ),
            submit_label="승인하고 입력 포인트 지급",
            default_note="",
            require_note=False,
            tone="green",
        )

        if response:
            return response

        default_note = f"작성하신 여행 루트가 승인되었습니다. {points}P가 지급되었습니다."

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="approve_with_custom_points",
            title="승인 포인트 직접 입력",
            description=(
                "선택한 여행 루트를 승인하고 작성자에게 원하는 만큼 포인트를 지급합니다. "
                f"기본값은 {DEFAULT_APPROVAL_POINTS}P입니다."
            ),
            submit_label="승인하고 입력 포인트 지급",
            default_note=default_note,
            require_note=False,
            point_amount=points,
            allow_custom_points=True,
            default_points=points,
            tone="green",
        )

        if response:
            return response

        return self._approve_and_award_points(request, queryset, points, review_note)

    @admin.action(description="승인 + 100P 지급")
    def approve_with_100_points(self, request, queryset):
        points = 100

        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="approve_with_100_points",
                title="승인 사유 입력",
                description=f"선택한 여행 루트를 승인하고 작성자에게 {points}P를 지급합니다.",
                submit_label=f"승인하고 {points}P 지급",
                default_note=f"작성하신 여행 루트가 승인되었습니다. {points}P가 지급되었습니다.",
                require_note=False,
                point_amount=points,
                tone="green",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="approve_with_100_points",
            title="승인 사유 입력",
            description=f"선택한 여행 루트를 승인하고 작성자에게 {points}P를 지급합니다.",
            submit_label=f"승인하고 {points}P 지급",
            default_note=f"작성하신 여행 루트가 승인되었습니다. {points}P가 지급되었습니다.",
            require_note=False,
            point_amount=points,
            tone="green",
        )

        if response:
            return response

        return self._approve_and_award_points(request, queryset, points, review_note)

    @admin.action(description="우수 루트 승인 + 300P 지급")
    def approve_with_300_points(self, request, queryset):
        points = 300

        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="approve_with_300_points",
                title="우수 루트 승인 사유 입력",
                description=f"선택한 여행 루트를 우수 루트로 승인하고 작성자에게 {points}P를 지급합니다.",
                submit_label=f"승인하고 {points}P 지급",
                default_note=f"정성스럽게 작성된 우수 여행 루트로 승인되었습니다. {points}P가 지급되었습니다.",
                require_note=False,
                point_amount=points,
                tone="green",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="approve_with_300_points",
            title="우수 루트 승인 사유 입력",
            description=f"선택한 여행 루트를 우수 루트로 승인하고 작성자에게 {points}P를 지급합니다.",
            submit_label=f"승인하고 {points}P 지급",
            default_note=f"정성스럽게 작성된 우수 여행 루트로 승인되었습니다. {points}P가 지급되었습니다.",
            require_note=False,
            point_amount=points,
            tone="green",
        )

        if response:
            return response

        return self._approve_and_award_points(request, queryset, points, review_note)

    @admin.action(description="대표 루트 승인 + 500P 지급")
    def approve_with_500_points(self, request, queryset):
        points = 500

        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="approve_with_500_points",
                title="대표 루트 승인 사유 입력",
                description=f"선택한 여행 루트를 대표 루트로 승인하고 작성자에게 {points}P를 지급합니다.",
                submit_label=f"승인하고 {points}P 지급",
                default_note=f"대표 여행 루트로 선정되었습니다. {points}P가 지급되었습니다.",
                require_note=False,
                point_amount=points,
                tone="green",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="approve_with_500_points",
            title="대표 루트 승인 사유 입력",
            description=f"선택한 여행 루트를 대표 루트로 승인하고 작성자에게 {points}P를 지급합니다.",
            submit_label=f"승인하고 {points}P 지급",
            default_note=f"대표 여행 루트로 선정되었습니다. {points}P가 지급되었습니다.",
            require_note=False,
            point_amount=points,
            tone="green",
        )

        if response:
            return response

        return self._approve_and_award_points(request, queryset, points, review_note)

    def _approve_and_award_points(self, request, queryset, points, review_note):
        success_count = 0
        already_awarded_count = 0
        error_count = 0
        no_author_count = 0

        selected_ids = self._get_selected_ids(queryset)

        if not selected_ids:
            self.message_user(
                request,
                "선택된 여행 루트가 없습니다.",
                messages.WARNING,
            )
            return

        with transaction.atomic():
            # 중요:
            # admin get_queryset()에는 Count annotate가 있어서 GROUP BY가 붙을 수 있습니다.
            # 또한 author__profile 같은 nullable 관계를 select_related로 붙인 상태에서
            # select_for_update()를 쓰면 PostgreSQL에서 아래 오류가 납니다.
            #
            # FOR UPDATE cannot be applied to the nullable side of an outer join
            #
            # 그래서 여기서는 admin queryset을 그대로 잠그지 않고,
            # 선택된 pk만 기준으로 Post 테이블 자기 자신만 잠급니다.
            posts = (
                Post.objects
                .filter(pk__in=selected_ids)
                .select_for_update(of=("self",))
                .order_by("pk")
            )

            for post in posts:
                if not post.author_id:
                    error_count += 1
                    no_author_count += 1
                    continue

                now = timezone.now()

                if post.points_awarded:
                    post.review_status = Post.ReviewStatus.APPROVED
                    post.review_note = review_note
                    post.review_notice_read = False
                    post.reviewed_by = request.user
                    post.reviewed_at = now
                    post.save(
                        update_fields=[
                            "review_status",
                            "review_note",
                            "review_notice_read",
                            "reviewed_by",
                            "reviewed_at",
                        ]
                    )
                    already_awarded_count += 1
                    continue

                try:
                    award_route_approved_points(
                        post=post,
                        points=points,
                        created_by=request.user,
                    )
                except ValidationError as exc:
                    error_count += 1
                    self.message_user(
                        request,
                        f"#{post.pk} 포인트 지급 중 오류: {exc}",
                        messages.WARNING,
                    )
                    continue

                post.review_status = Post.ReviewStatus.APPROVED
                post.review_note = review_note
                post.review_notice_read = False
                post.points_awarded = True
                post.awarded_points = points
                post.reviewed_by = request.user
                post.reviewed_at = now
                post.save(
                    update_fields=[
                        "review_status",
                        "review_note",
                        "review_notice_read",
                        "points_awarded",
                        "awarded_points",
                        "reviewed_by",
                        "reviewed_at",
                    ]
                )

                success_count += 1

        if error_count:
            level = messages.WARNING
        else:
            level = messages.SUCCESS

        extra_error_text = ""
        if no_author_count:
            extra_error_text = f" / 작성자 없음: {no_author_count}개"

        self.message_user(
            request,
            (
                f"승인 및 포인트 지급 완료: {success_count}개 / "
                f"이미 지급되어 승인 알림만 처리: {already_awarded_count}개 / "
                f"오류: {error_count}개"
                f"{extra_error_text}"
            ),
            level,
        )

    @admin.action(description="수정 요청으로 변경")
    def mark_needs_edit(self, request, queryset):
        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="mark_needs_edit",
                title="수정 요청 사유 입력",
                description="선택한 여행 루트를 수정 요청 상태로 바꾸고 사용자에게 사유를 안내합니다.",
                submit_label="수정 요청 보내기",
                default_note=(
                    "내용 보완이 필요합니다. 장소별 설명, 추천 이유, 실제 이동 흐름을 "
                    "조금 더 자세히 작성해주세요."
                ),
                require_note=True,
                tone="yellow",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="mark_needs_edit",
            title="수정 요청 사유 입력",
            description="선택한 여행 루트를 수정 요청 상태로 바꾸고 사용자에게 사유를 안내합니다.",
            submit_label="수정 요청 보내기",
            default_note=(
                "내용 보완이 필요합니다. 장소별 설명, 추천 이유, 실제 이동 흐름을 "
                "조금 더 자세히 작성해주세요."
            ),
            require_note=True,
            tone="yellow",
        )

        if response:
            return response

        updated = queryset.update(
            review_status=Post.ReviewStatus.NEEDS_EDIT,
            review_note=review_note,
            review_notice_read=False,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated}개 루트를 수정 요청 상태로 변경하고 사유를 저장했습니다.",
            messages.WARNING,
        )

    @admin.action(description="반려 처리")
    def reject_posts(self, request, queryset):
        if "apply_review_action" not in request.POST:
            return self._render_review_reason_form(
                request,
                queryset,
                action_name="reject_posts",
                title="반려 사유 입력",
                description="선택한 여행 루트를 반려하고 사용자에게 반려 사유를 안내합니다.",
                submit_label="반려 처리하기",
                default_note=(
                    "작성 내용이 부족하거나 실제 여행 루트로 보기 어려워 반려되었습니다. "
                    "장소 3개 이상과 각 장소별 설명을 자세히 작성해주세요."
                ),
                require_note=True,
                tone="red",
            )

        review_note, response = self._get_review_note_or_render_error(
            request,
            queryset,
            action_name="reject_posts",
            title="반려 사유 입력",
            description="선택한 여행 루트를 반려하고 사용자에게 반려 사유를 안내합니다.",
            submit_label="반려 처리하기",
            default_note=(
                "작성 내용이 부족하거나 실제 여행 루트로 보기 어려워 반려되었습니다. "
                "장소 3개 이상과 각 장소별 설명을 자세히 작성해주세요."
            ),
            require_note=True,
            tone="red",
        )

        if response:
            return response

        updated = queryset.update(
            review_status=Post.ReviewStatus.REJECTED,
            review_note=review_note,
            review_notice_read=False,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated}개 루트를 반려 처리하고 사유를 저장했습니다.",
            messages.ERROR,
        )

    @admin.action(description="검수중으로 되돌리기")
    def reset_to_pending(self, request, queryset):
        updated = queryset.filter(points_awarded=False).update(
            review_status=Post.ReviewStatus.PENDING,
            review_note="",
            review_notice_read=True,
            reviewed_by=None,
            reviewed_at=None,
        )

        self.message_user(
            request,
            f"{updated}개 루트를 검수중 상태로 되돌렸습니다. 이미 포인트가 지급된 글은 제외됩니다.",
            messages.INFO,
        )

    @admin.action(description="검수 결과 알림 다시 띄우기")
    def mark_notice_unread(self, request, queryset):
        updated = queryset.filter(
            review_status__in=[
                Post.ReviewStatus.APPROVED,
                Post.ReviewStatus.NEEDS_EDIT,
                Post.ReviewStatus.REJECTED,
            ]
        ).update(review_notice_read=False)

        self.message_user(
            request,
            f"{updated}개 루트의 검수 결과 알림을 다시 표시하도록 변경했습니다.",
            messages.INFO,
        )

    @admin.action(description="검수 결과 알림 확인 처리")
    def mark_notice_read(self, request, queryset):
        updated = queryset.update(review_notice_read=True)

        self.message_user(
            request,
            f"{updated}개 루트의 검수 결과 알림을 확인 처리했습니다.",
            messages.INFO,
        )


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "day",
        "visit_time_str",
        "place_name",
        "cost",
        "created_at",
    )

    list_filter = (
        "day",
        "created_at",
    )

    search_fields = (
        "place_name",
        "description",
        "post__title",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "ip_address",
        "viewed_on",
        "created_at",
    )

    list_filter = (
        "viewed_on",
        "created_at",
    )

    search_fields = (
        "post__title",
        "ip_address",
    )

    readonly_fields = (
        "post",
        "ip_address",
        "viewed_on",
        "created_at",
    )


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
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
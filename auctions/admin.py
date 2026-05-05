from django.contrib import admin
from .models import AuctionRequest, AuctionAnswer


class AuctionAnswerInline(admin.TabularInline):
    model = AuctionAnswer
    extra = 0
    fields = (
        "author",
        "title",
        "summary",
        "total_time",
        "total_cost",
        "is_selected",
        "is_active",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )


@admin.register(AuctionRequest)
class AuctionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author_display",
        "destination",
        "reward_points",
        "status",
        "answer_count",
        "deadline_at",
        "selected_answer",
        "created_at",
    )

    list_filter = (
        "status",
        "transport",
        "created_at",
        "deadline_at",
    )

    search_fields = (
        "title",
        "destination",
        "start_area",
        "request_detail",
        "author__username",
        "author__email",
        "author__profile__nickname",
    )

    readonly_fields = (
        "selected_answer",
        "selected_at",
        "refunded_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "기본 정보",
            {
                "fields": (
                    "author",
                    "title",
                    "start_area",
                    "destination",
                    "travel_date",
                    "people_count",
                    "transport",
                    "budget",
                    "request_detail",
                )
            },
        ),
        (
            "포인트 / 상태",
            {
                "fields": (
                    "reward_points",
                    "status",
                    "deadline_at",
                    "selected_answer",
                    "selected_at",
                    "refunded_at",
                    "is_active",
                )
            },
        ),
        (
            "시간",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = [AuctionAnswerInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "author",
            "author__profile",
            "selected_answer",
        )

    @admin.display(description="의뢰자")
    def author_display(self, obj):
        return obj.author_nickname

    @admin.display(description="답변수")
    def answer_count(self, obj):
        return obj.answers.filter(is_active=True).count()


@admin.register(AuctionAnswer)
class AuctionAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "author_display",
        "title",
        "is_selected",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_selected",
        "is_active",
        "created_at",
    )

    search_fields = (
        "title",
        "summary",
        "content",
        "request__title",
        "author__username",
        "author__email",
        "author__profile__nickname",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "request",
            "author",
            "author__profile",
        )

    @admin.display(description="답변자")
    def author_display(self, obj):
        return obj.author_nickname
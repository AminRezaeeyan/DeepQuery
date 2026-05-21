from django.contrib import admin
from django.utils import timezone
from .models import Plan, UserSubscription, UserUsage, Payment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "daily_message_limit",
        "daily_document_limit",
        "daily_image_limit",
    )

    search_fields = ("name",)

    fieldsets = (
        ("Plan Info", {
            "fields": ("name", "price")
        }),
        ("Daily Limits", {
            "fields": (
                "daily_message_limit",
                "daily_document_limit",
                "daily_image_limit",
            )
        }),
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "start_date",
        "end_date",
        "is_active",
    )

    search_fields = ("user__username", "user__email")
    list_filter = ("plan", "start_date")
    readonly_fields = ("is_active",)


@admin.register(UserUsage)
class UserUsageAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "message_count",
        "document_count",
        "image_count",
        "last_reset",
    )

    search_fields = ("user__username", "user__email")
    list_filter = ("last_reset",)

    actions = ["reset_usage"]

    def reset_usage(self, request, queryset):
        queryset.update(
            message_count=0,
            document_count=0,
            image_count=0,
            last_reset=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} usage records reset.")

    reset_usage.short_description = "Reset selected user usage"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "status",
        "authority",
        "ref_id",
        "created_at",
    )

    list_filter = ("status", "created_at", "plan")
    search_fields = ("user__username", "authority", "ref_id")
    readonly_fields = ("created_at",)

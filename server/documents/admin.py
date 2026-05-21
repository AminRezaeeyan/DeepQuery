from django.contrib import admin
from django.utils.html import format_html
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "short_uuid",
        "user",
        "chat_id",
        "source_type",
        "source_preview",
        "status_badge",
        "text_size",
        "created_at",
    )

    list_filter = (
        "source_type",
        "status",
        "created_at",
    )

    search_fields = (
        "uuid",
        "original_filename",
        "source_url",
        "user__email",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
        "text_preview",
    )

    autocomplete_fields = (
        "user",
        "chat",
    )

    actions = [
        "mark_processing",
        "mark_done",
        "mark_failed",
    ]

    ordering = ("-created_at",)

    fieldsets = (
        ("Document Info", {
            "fields": (
                "uuid",
                "user",
                "chat",
                "source_type",
            )
        }),

        ("Source", {
            "fields": (
                "file",
                "original_filename",
                "source_url",
            )
        }),

        ("Processing", {
            "fields": (
                "status",
                "extracted_text",
                "text_preview",
            )
        }),

        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    # ---------- Display helpers ----------

    def short_uuid(self, obj):
        return str(obj.uuid)[:8]

    short_uuid.short_description = "ID"

    def chat_id(self, obj):
        return str(obj.chat_id)[:8] if obj.chat_id else "-"

    chat_id.short_description = "Chat"

    def source_preview(self, obj):

        if obj.source_type == Document.SourceTypeChoices.WEB:
            if obj.source_url:
                return format_html(
                    '<a href="{}" target="_blank">Open Page</a>',
                    obj.source_url
                )
            return "-"

        if obj.file:
            return format_html(
                '<a href="{}">Download</a>',
                obj.file.url
            )

        return "-"

    source_preview.short_description = "Source"

    def status_badge(self, obj):

        colors = {
            "pending": "#999",
            "processing": "#ff9800",
            "done": "#4caf50",
            "failed": "#f44336",
        }

        return format_html(
            '<b style="color:{}">{}</b>',
            colors.get(obj.status, "#999"),
            obj.get_status_display()
        )

    status_badge.short_description = "Status"

    def text_size(self, obj):
        return f"{len(obj.extracted_text)} chars"

    text_size.short_description = "Text Size"

    def text_preview(self, obj):
        if not obj.extracted_text:
            return "-"
        return obj.extracted_text[:500] + ("..." if len(obj.extracted_text) > 500 else "")

    text_preview.short_description = "Extracted Preview"

    # ---------- Admin actions ----------

    def mark_processing(self, request, queryset):
        queryset.update(status=Document.StatusChoices.PROCESSING)
        self.message_user(request, f"{queryset.count()} documents marked as processing.")

    mark_processing.short_description = "Mark as processing"

    def mark_done(self, request, queryset):
        queryset.update(status=Document.StatusChoices.DONE)
        self.message_user(request, f"{queryset.count()} documents marked as done.")

    mark_done.short_description = "Mark as done"

    def mark_failed(self, request, queryset):
        queryset.update(status=Document.StatusChoices.FAILED)
        self.message_user(request, f"{queryset.count()} documents marked as failed.")

    mark_failed.short_description = "Mark as failed"

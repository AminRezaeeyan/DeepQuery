from django.contrib import admin
from django.utils.html import format_html
from .models import Chat, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = (
        "role",
        "content_preview",
        "image_preview",
        "created_at",
        "edited_at",
        "is_deleted",
    )
    readonly_fields = (
        "content_preview",
        "image_preview",
        "created_at",
        "edited_at",
    )
    can_delete = False
    show_change_link = True

    def content_preview(self, obj):
        if not obj.content:
            return "-"
        return obj.content[:120] + ("..." if len(obj.content) > 120 else "")
    content_preview.short_description = "Content"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:6px;" />',
                obj.image.url,
            )
        return "-"
    image_preview.short_description = "Image"


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):

    list_display = (
        "short_uuid",
        "user",
        "title",
        "message_count",
        "is_temporary",
        "is_deleted",
        "updated_at",
    )

    list_filter = (
        "is_temporary",
        "is_deleted",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "uuid",
        "title",
        "user__email",
    )

    

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
        "deleted_at",
        "message_count",
    )

    inlines = [MessageInline]

    ordering = ("-updated_at",)

    actions = [
        "soft_delete_chats",
        "restore_chats",
    ]

    fieldsets = (
        ("Chat Info", {
            "fields": (
                "uuid",
                "user",
                "title",
                "provider_id",
            )
        }),

        ("State", {
            "fields": (
                "is_temporary",
                "is_deleted",
                "deleted_at",
            )
        }),

        ("Stats", {
            "fields": (
                "message_count",
                "created_at",
                "updated_at",
            )
        }),
    )

    def get_queryset(self, request):
        # The default manager hides deleted chats, which made them impossible to restore.
        return Chat.all_objects.all()

    def short_uuid(self, obj):
        return str(obj.uuid)[:8]
    short_uuid.short_description = "Chat ID"

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"

    def soft_delete_chats(self, request, queryset):
        for chat in queryset:
            chat.mark_deleted()
        self.message_user(request, f"{queryset.count()} chats soft deleted.")

    soft_delete_chats.short_description = "Soft delete selected chats"

    def restore_chats(self, request, queryset):
        for chat in queryset:
            chat.restore()
        self.message_user(request, f"{queryset.count()} chats restored.")

    restore_chats.short_description = "Restore deleted chats"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):

    list_display = (
        "short_uuid",
        "chat",
        "role",
        "content_preview",
        "has_image",
        "created_at",
        "is_deleted",
    )

    list_filter = (
        "role",
        "is_deleted",
        "created_at",
    )

    search_fields = (
        "uuid",
        "content",
        "chat__uuid",
        "chat__user__email",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "edited_at",
        "image_preview",
    )

    ordering = ("-created_at",)

    actions = [
        "soft_delete_messages",
    ]

    fieldsets = (
        ("Message Info", {
            "fields": (
                "uuid",
                "chat",
                "role",
            )
        }),

        ("Content", {
            "fields": (
                "content",
                "image",
                "image_preview",
            )
        }),

        ("State", {
            "fields": (
                "is_deleted",
                "created_at",
                "edited_at",
            )
        }),
    )

    def short_uuid(self, obj):
        return str(obj.uuid)[:8]

    short_uuid.short_description = "Message ID"

    def content_preview(self, obj):
        return obj.content[:80] + ("..." if len(obj.content) > 80 else "")

    content_preview.short_description = "Content"

    def has_image(self, obj):
        return bool(obj.image)

    has_image.boolean = True
    has_image.short_description = "Image"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:200px;border-radius:8px;" />',
                obj.image.url,
            )
        return "-"
    image_preview.short_description = "Preview"

    def soft_delete_messages(self, request, queryset):
        queryset.update(is_deleted=True)
        self.message_user(request, f"{queryset.count()} messages soft deleted.")

    soft_delete_messages.short_description = "Soft delete selected messages"

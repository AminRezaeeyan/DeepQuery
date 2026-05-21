from django.contrib import admin
from django.utils.html import format_html
from .models import (
    LLMProvider,
    AITaskConfig,
    EmbeddingProvider,
    EmbeddedObject,
    EmbeddingChunk,
    MemoryFact,
)

@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "provider_type",
        "model_name",
        "supports_vision",
        "context_limit",
        "task_count",
        "created_at",
    )

    list_filter = (
        "provider_type",
        "supports_vision",
    )

    search_fields = (
        "name",
        "model_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Provider", {
            "fields": (
                "name",
                "provider_type",
                "model_name",
            )
        }),

        ("Connection", {
            "fields": (
                "api_key",
                "base_url",
            )
        }),

        ("Capabilities", {
            "fields": (
                "max_context_tokens",
                "supports_vision",
            )
        }),

        ("Advanced Config", {
            "fields": (
                "config",
            ),
            "classes": ("collapse",),
        }),

        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def task_count(self, obj):
        return obj.task_configs.count()

    task_count.short_description = "Tasks"


@admin.register(AITaskConfig)
class AITaskConfigAdmin(admin.ModelAdmin):

    list_display = (
        "task_type",
        "provider",
        "provider_type",
        "model_name",
        "is_default_for_chat",
    )

    list_filter = (
        "task_type",
        "is_default_for_chat",
        "provider__provider_type",
    )

    search_fields = (
        "provider__name",
        "provider__model_name",
    )

    autocomplete_fields = ["provider"]

    def provider_type(self, obj):
        return obj.provider.provider_type

    provider_type.short_description = "Provider"

    def model_name(self, obj):
        return obj.provider.model_name

    model_name.short_description = "Model"




@admin.register(EmbeddingProvider)
class EmbeddingProviderAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "provider_type",
        "model_name",
        "dimension",
        "status_badge",
        "is_active",
        "is_serving",
        "embedded_count",
    )

    list_filter = (
        "provider_type",
        "status",
        "is_active",
        "is_serving",
    )

    search_fields = (
        "name",
        "model_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = [
        "set_active",
        "set_serving",
    ]

    fieldsets = (
        ("Provider", {
            "fields": (
                "name",
                "provider_type",
                "model_name",
            )
        }),

        ("Connection", {
            "fields": (
                "api_key",
                "base_url",
            )
        }),

        ("Embedding Config", {
            "fields": (
                "dimension",
                "max_tokens",
            )
        }),

        ("Status", {
            "fields": (
                "status",
                "status_message",
                "is_active",
                "is_serving",
            )
        }),

        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def status_badge(self, obj):

        colors = {
            "ready": "green",
            "downloading": "orange",
            "error": "red",
            "reembedding": "purple",
        }

        return format_html(
            '<b style="color:{}">{}</b>',
            colors.get(obj.status, "gray"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def embedded_count(self, obj):
        return obj.embedded_objects.count()

    embedded_count.short_description = "Objects"

    def set_active(self, request, queryset):
        for provider in queryset:
            provider.is_active = True
            provider.save()

    def set_serving(self, request, queryset):
        for provider in queryset:
            provider.is_serving = True
            provider.save()





class EmbeddingChunkInline(admin.TabularInline):
    model = EmbeddingChunk
    extra = 0
    fields = (
        "chunk_index",
        "token_count",
        "text_preview",
    )
    readonly_fields = (
        "chunk_index",
        "token_count",
        "text_preview",
    )
    can_delete = False

    def text_preview(self, obj):
        return obj.text[:120] + ("..." if len(obj.text) > 120 else "")

    text_preview.short_description = "Text"




@admin.register(EmbeddedObject)
class EmbeddedObjectAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "provider",
        "content_type",
        "object_id",
        "chunk_count",
        "created_at",
    )

    list_filter = (
        "provider",
        "content_type",
    )

    search_fields = (
        "object_id",
        "tag",
    )

    readonly_fields = (
        "created_at",
    )

    inlines = [EmbeddingChunkInline]

    def chunk_count(self, obj):
        return obj.chunks.count()

    chunk_count.short_description = "Chunks"


@admin.register(EmbeddingChunk)
class EmbeddingChunkAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "embedded_object",
        "chunk_index",
        "token_count",
        "created_at",
    )

    list_filter = (
        "embedded_object__provider",
    )

    search_fields = (
        "text",
    )

    readonly_fields = (
        "created_at",
    )





@admin.register(MemoryFact)
class MemoryFactAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "chat_id",
        "fact_preview",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "fact",
        "user__email",
        "user__username",
    )

    readonly_fields = (
        "created_at",
    )

    def fact_preview(self, obj):
        return obj.fact[:100] + ("..." if len(obj.fact) > 100 else "")

    fact_preview.short_description = "Fact"

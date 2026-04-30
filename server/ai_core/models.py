from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from pgvector.django import VectorField


class LLMProvider(models.Model):

    PROVIDER_CHOICES = [
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("claude", "Claude"),
        ("ollama", "Ollama"),
    ]

    name = models.CharField(max_length=100)

    provider_type = models.CharField(max_length=20,choices=PROVIDER_CHOICES)

    api_key = models.CharField(max_length=255,blank=True,null=True)

    base_url = models.URLField(blank=True,null=True)

    model_name = models.CharField(max_length=100)

    config = models.JSONField(blank=True,null=True)

    max_context_tokens = models.PositiveIntegerField(
        default=16000,
        help_text="Maximum context window for this model"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):

        if self.task_configs.exists():
            raise ValidationError(
                "This provider is assigned to one or more tasks and cannot be deleted. "
                "Please reassign or remove those tasks first."
            )

        super().delete(*args, **kwargs)

    @property
    def context_limit(self):   
        return self.max_context_tokens


    def __str__(self):
        return f"{self.name} ({self.provider_type})"
    


class AITaskConfig(models.Model):

    TASK_CHOICES = [
        ("chat", "Chat"),
        ("title_generation", "Chat Title Generation"),
        ("summarization", "Summarization"),
        ("fact_extraction", "Fact Extraction"),
        ("embedding", "Embedding Generation"),
    ]

    task_type = models.CharField(max_length=50, choices=TASK_CHOICES)

    provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.PROTECT,
        related_name="task_configs",
    )

    is_default_for_chat = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # (task_type, provider) must be unique
            models.UniqueConstraint(
                fields=["task_type", "provider"],
                name="unique_task_provider_pair",
            ),

            # Only chat can have is_default_for_chat=True
            models.CheckConstraint(
                condition=Q(is_default_for_chat=False) | Q(task_type="chat"),
                name="default_flag_chat_only",
            ),
        ]

    def clean(self):

        # Non-chat tasks must only have one provider
        if self.task_type != "chat":
            exists = (
                AITaskConfig.objects.exclude(id=self.id)
                .filter(task_type=self.task_type)
                .exists()
            )
            if exists:
                raise ValidationError(
                    f"Task '{self.task_type}' may only have one assigned provider."
                )


    def save(self, *args, **kwargs):
        is_new = self._state.adding

        self.full_clean()
        super().save(*args, **kwargs)

        # Only one default chat provider
        if self.task_type == "chat" and self.is_default_for_chat:
            AITaskConfig.objects.filter(
                task_type="chat"
            ).exclude(id=self.id).update(is_default_for_chat=False)

        # Auto-populate all task configs if first-ever entry
        if is_new:
            self._auto_populate_if_first_provider()

 
    def _auto_populate_if_first_provider(self):
        provider = self.provider

        # Only run if this provider is the ONLY provider in the system
        if LLMProvider.objects.count() != 1:
            return 

        # If auto-population was already done, skip
        if AITaskConfig.objects.count() > 1:
            return

        for task, _ in self.TASK_CHOICES:
            if task == "chat":
                AITaskConfig.objects.update_or_create(
                    task_type=task,
                    defaults={"provider": provider, "is_default_for_chat": True},
                )
            else:
                AITaskConfig.objects.update_or_create(
                    task_type=task,
                    defaults={"provider": provider},
                )


class EmbeddingProvider(models.Model):
    PROVIDER_TYPE_CHOICES = [
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("hf_local", "Hugging Face Local"),
    ]

    STATUS_CHOICES = [
        ("ready", "Ready"),
        ("downloading", "Downloading"),
        ("error", "Error"),
         ("reembedding", "Re-embedding"),
    ]

    name = models.CharField(max_length=100, unique=True)

    provider_type = models.CharField(
        max_length=50,
        choices=PROVIDER_TYPE_CHOICES
    )

    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="API key for API-based providers"
    )

    base_url = models.URLField(blank=True,null=True)

    model_name = models.CharField(
        max_length=255,
        help_text="Model name (e.g. 'text-embedding-3-large' or 'all-mpnet-base-v2')"
    )

    dimension = models.PositiveIntegerField()

    max_tokens = models.PositiveIntegerField(default=512)

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="ready"
    )

    status_message = models.TextField(
        blank=True,
        help_text="More details about errors or download state."
    )

    is_active = models.BooleanField(
        default=False,
        help_text="The only provider used for live search + new embeddings."
    )

    is_serving = models.BooleanField(
        default=False,
        help_text="The provider currently used for queries."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.name} ({self.provider_type}) [{self.get_status_display()}]"


    def clean(self):

        if not self.model_name:
            raise ValidationError("model_name is required for all embedding providers.")

        if self.provider_type != "hf_local":
            if not self.api_key:
                raise ValidationError(
                    f"API key is required for provider type '{self.provider_type}'."
                )

            if self.status == "downloading":
                raise ValidationError(
                    "Only local providers can have 'downloading' status."
                )

        # only one active provider
        if self.is_active:
            EmbeddingProvider.objects.exclude(pk=self.pk).update(is_active=False)

        # only one serving provider
        if self.is_serving:
            qs = EmbeddingProvider.objects.filter(is_serving=True).exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "Only one embedding provider can be serving at a time."
            )

    def save(self, *args, **kwargs):

        is_new = self.pk is None
        old_instance = None
        if not is_new:
            old_instance = EmbeddingProvider.objects.filter(pk=self.pk).first()
            old_status = old_instance.status
        
        self.full_clean()

        # If no other providers exist, force the first one to be active and serving
        if is_new and not EmbeddingProvider.objects.exists():
            self.is_active = True
            self.is_serving = True

        super().save(*args, **kwargs)

        # Handle local HF model download
        if self.provider_type == "hf_local":

            trigger_download = False

            if is_new:
                trigger_download = True

            elif old_instance and old_instance.status == "error":
                trigger_download = True

            elif old_instance and old_instance.model_name != self.model_name:
                trigger_download = True


            if trigger_download:
                from .tasks import download_embedding_model
                download_embedding_model.delay(self.id)

         # Handle provider change
        if old_instance and not old_instance.is_active and self.is_active:
            self.start_reembedding_cycle()


    def delete(self, *args, **kwargs):
        if self.status == "reembedding":
            raise ValidationError("Cannot delete a provider while re-embedding is running.")
        if self.is_serving:
            raise ValidationError("Cannot delete provider currently serving embeddings.")
        if self.is_active:
            raise ValidationError("Cannot delete the active embedding provider.")
        

        return super().delete(*args, **kwargs)
    
    
    def start_reembedding_cycle(self):

        from .tasks import reembed_all_objects

        self.status = "reembedding"
        self.status_message = "Starting re-embedding process..."
        super().save(update_fields=["status", "status_message"])

        reembed_all_objects.delay(self.id)



class EmbeddedObject(models.Model):

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    object_id = models.CharField(max_length=255)

    target = GenericForeignKey("content_type", "object_id")

    provider = models.ForeignKey(
        EmbeddingProvider,
        on_delete=models.PROTECT,
        related_name="embedded_objects"
    )

    tag = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.target}"
    

class EmbeddingChunk(models.Model):

    embedded_object = models.ForeignKey(
        EmbeddedObject,
        on_delete=models.CASCADE,
        related_name="chunks"
    )

    text = models.TextField()

    embedding = VectorField()

    chunk_index = models.PositiveIntegerField()

    token_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]

    def __str__(self):
        return f"Chunk {self.chunk_index}"


class MemoryFact(models.Model):
    chat_id = models.IntegerField(null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memory_facts"
    )

    fact = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]




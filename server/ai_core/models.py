from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q

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
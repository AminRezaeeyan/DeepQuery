from django.db import models


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

    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_active:
            LLMProvider.objects.exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.provider_type})"

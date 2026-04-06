from django.db import models
from django.conf import settings
import uuid


class Chat(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chats"
    )

    provider_id = models.IntegerField(null=True, blank=True)

    title = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat {self.uuid}"


class Message(models.Model):

    class Role(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    chat = models.ForeignKey(
        Chat,
        related_name="messages",
        on_delete=models.CASCADE
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} message in {self.chat_id}"
    
    class Meta:
        ordering = ['-created_at']

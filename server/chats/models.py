from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

from chats.managers import ChatManager, MessageManager


class Chat(models.Model):
    objects = ChatManager()        # hides deleted chats
    all_objects = models.Manager() # shows everything
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chats"
    )

    provider_id = models.IntegerField(null=True, blank=True)

    title = models.CharField(max_length=255, blank=True, default='New chat')

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True)
                                     
    is_deleted = models.BooleanField(default=False)

    def mark_updated(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])

    def mark_deleted(self):
        if self.is_deleted:
            return
        
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

        # soft delete cascade
        self.messages.update(is_deleted=True)

    def __str__(self):
        return f"Chat {self.uuid}"


class Message(models.Model):
    objects = MessageManager()     # hides deleted chats
    all_objects = models.Manager() # shows everything

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
    
    edited_at = models.DateTimeField(null=True, blank=True)
                                     
    is_deleted = models.BooleanField(default=False)

    def mark_edited(self):
        self.is_deleted = True
        self.edited_at = timezone.now()
        self.save(update_fields=["is_deleted", "edited_at"])

    def mark_deleted(self):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        return f"{self.role} message in {self.chat_id}"
    
    class Meta:
        ordering = ['-created_at']

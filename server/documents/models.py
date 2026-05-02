import uuid
from django.db import models
from django.conf import settings

class Document(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)    
    chat = models.ForeignKey(
        "chats.Chat",
        to_field="uuid",
        related_name="documents",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to="user_documents/")
    original_filename = models.CharField(max_length=255, blank=True)
    
    # We only store extracted text if it's small/necessary for RAG inspection
    extracted_text = models.TextField(blank=True)
    
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

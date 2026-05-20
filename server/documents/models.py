import uuid
from django.db import models
from django.conf import settings

class Document(models.Model):
    class SourceTypeChoices(models.TextChoices):
        FILE = "file", "Uploaded File"
        WEB = "web", "Web Page"

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)    
    chat = models.ForeignKey(
        "chats.Chat",
        to_field="uuid",
        related_name="documents",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # 1. Add a type indicator
    source_type = models.CharField(max_length=10, choices=SourceTypeChoices.choices, default=SourceTypeChoices.FILE)
    
    # 2. Make file upload optional (since web pages don't have files)
    file = models.FileField(upload_to="user_documents/", blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    
    # 3. Add a field for web URLs
    source_url = models.URLField(max_length=2000, blank=True, null=True)
    
    extracted_text = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.source_type == self.SourceTypeChoices.WEB:
            return f"Web: {self.source_url}"
        return f"File: {self.original_filename}"

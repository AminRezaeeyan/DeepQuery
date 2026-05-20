from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True) # Free, Starter, Pro, Business
    price = models.PositiveIntegerField(help_text="Price in Toman")
    daily_message_limit = models.PositiveIntegerField()
    daily_document_limit = models.PositiveIntegerField()

    def __str__(self):
        return self.name

class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.RESTRICT)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    @property
    def is_active(self):
        if not self.end_date:
            return True # Free plans might not expire
        return timezone.now() <= self.end_date

class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True)
    amount = models.PositiveIntegerField()
    authority = models.CharField(max_length=100, blank=True, null=True) # ZarinPal authority
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

from django.db import models
from django.conf import settings
from django.utils import timezone


class UserUsage(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        related_name='usage',
        on_delete=models.CASCADE
    )
    message_count = models.PositiveIntegerField(default=0)
    document_count = models.PositiveIntegerField(default=0)
    image_count = models.PositiveIntegerField(default=0)
    
    last_reset = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Usage for {self.user.id}"

    class Meta:
        verbose_name = "User Usage"
        verbose_name_plural = "User Usages"


class Plan(models.Model):
    class PlanType(models.TextChoices):
        FREE = "FREE", "Free"
        STARTER = "STARTER", "Starter"
        PRO = "PRO", "Pro"
        BUSINESS = "BUSINESS", "Business"

    name = models.CharField(max_length=50, unique=True, choices=PlanType.choices)
    price = models.PositiveIntegerField(help_text="Price in IRR")
    daily_message_limit = models.PositiveIntegerField(default=10)
    daily_document_limit = models.PositiveIntegerField(default=2)
    daily_image_limit = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name

class UserSubscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.RESTRICT)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    @property
    def is_active(self):
        if not self.end_date:
            return True # Free plans does not expire
        return timezone.now() <= self.end_date

class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True)
    amount = models.PositiveIntegerField()
    authority = models.CharField(max_length=100, blank=True, null=True) # ZarinPal authority
    ref_id = models.CharField(max_length=100, blank=True, null=True)
    fee = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

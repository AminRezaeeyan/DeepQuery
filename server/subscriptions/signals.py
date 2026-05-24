from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserSubscription, Plan


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_subscription(sender, instance, created, **kwargs):
    if created:
        free_plan = Plan.objects.get(name=Plan.PlanType.FREE)

        UserSubscription.objects.create(
            user=instance,
            plan=free_plan)

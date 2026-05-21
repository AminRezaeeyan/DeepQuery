from datetime import timedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Plan, UserSubscription, Payment, UserUsage
from chats.models import Message
from zarinpal import ZarinPal

class SubscriptionLimitExceeded(PermissionDenied):
    pass

class ZarinpalConfig:
    def __init__(self, merchant_id, sandbox, access_token):
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        self.access_token = access_token


def get_zarinpal():
    config = ZarinpalConfig(
        merchant_id=settings.ZARINPAL_MERCHANT_ID,
        sandbox=settings.ZARINPAL_SANDBOX,
        access_token=settings.ZARINPAL_ACCESS_TOKEN
    )
    return ZarinPal(config)


class SubscriptionService:
    @staticmethod
    def get_user_plan(user):
        try:
            sub = user.subscription
            if sub.is_active:
                return sub.plan
        except ObjectDoesNotExist:
            pass
        
        # Fallback to free plan if no active subscription
        free_plan = Plan.objects.get(name="Free")
        return free_plan
    
    @staticmethod
    def get_usage(user):
        usage, _ = UserUsage.objects.get_or_create(user=user)

        now = timezone.now()

        if usage.last_reset < now - timedelta(days=1):
            usage.messages_used = 0
            usage.documents_used = 0
            usage.images_used = 0
            usage.last_reset = now
            usage.save()
            
        return usage
    
    @staticmethod
    def check_limit(user, limit_field):
        plan = SubscriptionService.get_user_plan(user)
        usage = SubscriptionService.get_usage(user)

        plan_limit = getattr(plan, limit_field)
        usage_value = getattr(usage, f"{limit_field.replace('_limit', '')}_used")

        if usage_value >= plan_limit:
            raise SubscriptionLimitExceeded(
                f"You have reached your {limit_field.replace('_limit', '')} limit "
                f"({plan_limit}). Upgrade your plan."
            )

    @staticmethod
    def check_message_limit(user):
        SubscriptionService.check_limit(user, "daily_message_limit")

    @staticmethod
    def check_document_limit(user):
        SubscriptionService.check_limit(user, "document_limit")

    @staticmethod
    def check_image_limit(user):
        SubscriptionService.check_limit(user, "image_limit")


    @staticmethod
    @transaction.atomic
    def increment_usage(user, resource_type):
        usage = SubscriptionService.get_usage(user)

        if resource_type == "message":
            usage.messages_used += 1
        elif resource_type == "document":
            usage.documents_used += 1
        elif resource_type == "image":
            usage.images_used += 1
        else:
            raise ValidationError("Invalid resource type")

        usage.save()

    @staticmethod
    def initiate_zarinpal_payment(user, plan, request):
        callback_url = request.build_absolute_uri(reverse('payment-verify'))

        payment = Payment.objects.create(
            user=user,
            plan=plan,
            amount=plan.price,
            status=Payment.Status.PENDING
        )

        try:
            zarinpal = get_zarinpal()

            response = zarinpal.payments.create({
            "amount": int(plan.price), 
            "callback_url": callback_url, 
            "description": f"Subscription for {plan.name} plan", 
            "mobile": "09123456789",  
            "email": "customer@example.com",  
            "cardPan": ["6219861034529007", "5022291073776543"], 
            "referrer_id": "affiliate123", 
            })

            if "data" in response and "authority" in response["data"]:
                authority = response["data"]["authority"]
                payment_url = zarinpal.payments.generate_payment_url(authority)
                payment.authority = authority
                payment.save()

                return {
                    "payment_url": payment_url,
                    "authority": authority
                }
            else:
                error_message = response.get("message", "Unknown error from payment gateway")
                payment.status = Payment.Status.FAILED
                payment.save()
                raise ValidationError(f"Could not connect to payment gateway: {error_message}")

        except Exception as e:
            payment.status = Payment.Status.FAILED
            payment.save()
            raise ValidationError(f"An unexpected error occurred: {str(e)}")


    @staticmethod
    @transaction.atomic
    def verify_zarinpal_payment(authority: str, status: str):
        if status != "OK":
            raise ValidationError("Payment was canceled by the user.")

        try:
            payment = Payment.objects.get(authority=authority, status=Payment.Status.PENDING)
        except Payment.DoesNotExist:
            raise ValidationError("Invalid payment authority or payment already processed.")

        try:
            zarinpal = get_zarinpal()

            response = zarinpal.verifications.verify({
                    "amount": int(payment.amount),
                    "authority": authority,
                })
            

            # Status 100 means success. Status 101 means success but verified before.
            if response.get("status") in [100, 101]:
                payment.status = Payment.Status.SUCCESS
                payment.ref_id = response["data"]["ref_id"]
                payment.fee = response["data"]["fee"]
                payment.save()

                user = payment.user
                plan = payment.plan

                # Deactivate any existing active subscriptions for this user
                UserSubscription.objects.filter(user=user, is_active=True).update(is_active=False)

                # Create the new subscription
                UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    start_date=timezone.now().date(),
                    end_date=timezone.now().date() + timedelta(days=30),
                    is_active=True
                )
                return {"message": "Payment successful. Subscription updated.", "ref_id": payment.ref_id}
            else:
                payment.status = Payment.Status.FAILED
                payment.save()
                error_message = response.get("message", "Payment verification failed.")
                raise ValidationError(error_message)

        except Exception as e:
            payment.status = Payment.Status.FAILED
            payment.save()
            raise ValidationError(f"An unexpected error occurred during verification: {str(e)}")

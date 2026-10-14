import functools
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Plan, UserSubscription, Payment, UserUsage
from zarinpal import ZarinPal

# Seconds per request to the payment gateway.
ZARINPAL_TIMEOUT = 15

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
    zarinpal = ZarinPal(config)
    # The SDK's sessions have no timeout; give every request one.
    for session in (zarinpal.http_client, zarinpal.graphql_client):
        session.request = functools.partial(session.request, timeout=ZARINPAL_TIMEOUT)
    return zarinpal


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
        free_plan = Plan.objects.get(name=Plan.PlanType.FREE)
        return free_plan
    
    @staticmethod
    def get_usage(user):
        usage, _ = UserUsage.objects.get_or_create(user=user)

        now = timezone.now()

        if usage.last_reset < now - timedelta(days=1):
            usage.message_count = 0
            usage.document_count = 0
            usage.image_count = 0
            usage.last_reset = now
            usage.save()
            
        return usage
    
    RESOURCES = ("message", "document", "image")

    @staticmethod
    @transaction.atomic
    def consume(user, resource):
        """
        Counts one use of `resource` against today's limit, or raises
        SubscriptionLimitExceeded. Checking and counting happen under a row
        lock, so parallel requests can't both take the last slot.
        """
        if resource not in SubscriptionService.RESOURCES:
            raise ValidationError("Invalid resource type")

        SubscriptionService.get_usage(user)
        usage = UserUsage.objects.select_for_update().get(user=user)
        plan = SubscriptionService.get_user_plan(user)

        limit = getattr(plan, f"daily_{resource}_limit")
        field = f"{resource}_count"

        if getattr(usage, field) >= limit:
            raise SubscriptionLimitExceeded(
                f"You have reached your daily {resource} limit ({limit}). Upgrade your plan."
            )

        UserUsage.objects.filter(pk=usage.pk).update(**{field: F(field) + 1})

    @staticmethod
    def refund(user, resource):
        """Gives back a use when the request it paid for didn't complete."""
        field = f"{resource}_count"
        UserUsage.objects.filter(user=user, **{f"{field}__gt": 0}).update(**{field: F(field) - 1})

    @staticmethod
    def initiate_zarinpal_payment(user, plan):
        # ZarinPal sends the user back to the client, which verifies the
        # payment through the API and shows the result.
        callback_url = f"{settings.CLIENT_URL.rstrip('/')}/payment/result"

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

        # Reloading the result page verifies again: report the earlier success.
        done = Payment.objects.select_related("plan").filter(authority=authority, status=Payment.Status.SUCCESS).first()
        if done:
            return {"message": "Payment successful. Subscription updated.", "ref_id": str(done.ref_id), "plan": done.plan.name}

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

                # A user has exactly one subscription row: move it to the paid plan.
                now = timezone.now()
                UserSubscription.objects.update_or_create(
                    user=user,
                    defaults={"plan": plan, "start_date": now, "end_date": now + timedelta(days=30)},
                )
                return {"message": "Payment successful. Subscription updated.", "ref_id": str(payment.ref_id), "plan": plan.name}
            else:
                payment.status = Payment.Status.FAILED
                payment.save()
                error_message = response.get("message", "Payment verification failed.")
                raise ValidationError(error_message)

        except Exception as e:
            payment.status = Payment.Status.FAILED
            payment.save()
            raise ValidationError(f"An unexpected error occurred during verification: {str(e)}")

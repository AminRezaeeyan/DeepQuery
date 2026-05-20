from datetime import timedelta
from django.conf import settings
from django.forms import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied
from .models import Plan, UserSubscription, Payment
from chats.models import Message
from zarinpal import ZarinPal

class SubscriptionLimitExceeded(PermissionDenied):
    pass

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
        free_plan, _ = Plan.objects.get_or_create(
            name="Free", 
            defaults={"price": 0, "daily_message_limit": 10, "daily_document_limit": 2}
        )
        return free_plan

    @staticmethod
    def check_message_limit(user):
        plan = SubscriptionService.get_user_plan(user)
        today = timezone.now().date()
        
        # Count user messages sent today
        messages_today = Message.objects.filter(
            chat__user=user,
            role=Message.Role.USER,
            created_at__date=today
        ).count()

        if messages_today >= plan.daily_message_limit:
            raise SubscriptionLimitExceeded(f"Daily message limit ({plan.daily_message_limit}) reached. Please upgrade your plan.")

    def initiate_zarinpal_payment(self, user, plan, request):
        """
        Initiates a real payment request with Zarinpal.
        """
        callback_url = request.build_absolute_uri(reverse('subscriptions:payment-verify'))

        payment = Payment.objects.create(
            user=user,
            plan=plan,
            amount=plan.price,
            status=Payment.PaymentStatus.PENDING
        )

        try:
            zarinpal = ZarinPal(
                merchant_id=settings.ZARINPAL_MERCHANT_ID,
                sandbox=settings.ZARINPAL_SANDBOX,
            )

            response = zarinpal.payment_request(
                amount=int(plan.price),
                description=f"Subscription for {plan.name} plan",
                callback_url=callback_url,
                email=user.email,
                mobile=getattr(user, 'phone_number', '')
            )

            # Check if the request was successful
            if response.get("status") == 100 and "authority" in response:
                authority = response["authority"]
                payment.authority = authority
                payment.save()
                
                payment_url = zarinpal.get_payment_url(authority)
                return {
                    "payment_url": payment_url,
                    "authority": authority
                }
            else:
                # If Zarinpal returns an error, mark our payment as failed
                error_message = response.get("message", "Unknown error from payment gateway")
                payment.status = Payment.PaymentStatus.FAILED
                payment.save()
                raise ValidationError(f"Could not connect to payment gateway: {error_message}")

        except Exception as e:
            payment.status = Payment.PaymentStatus.FAILED
            payment.save()
            raise ValidationError(f"An unexpected error occurred: {str(e)}")

    @transaction.atomic
    def verify_zarinpal_payment(self, authority: str, status: str):
        """
        Verifies a payment with Zarinpal using the authority and status from the callback.
        """
        if status != "OK":
            raise ValidationError("Payment was canceled by the user.")

        try:
            payment = Payment.objects.get(authority=authority, status=Payment.PaymentStatus.PENDING)
        except Payment.DoesNotExist:
            raise ValidationError("Invalid payment authority or payment already processed.")

        try:
            zarinpal = ZarinPal(
                merchant_id=settings.ZARINPAL_MERCHANT_ID,
                sandbox=settings.ZARINPAL_SANDBOX,
            )
            # Amount should be in Tomans
            response = zarinpal.payment_verification(int(payment.amount), authority)

            # Status 100 means success. Status 101 means success but verified before.
            if response.get("status") in [100, 101]:
                payment.status = Payment.PaymentStatus.SUCCESS
                payment.ref_id = response.get('ref_id')
                payment.save()

                # Payment is successful, now create or update the user's subscription
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
                # Payment failed
                payment.status = Payment.PaymentStatus.FAILED
                payment.save()
                error_message = response.get("message", "Payment verification failed.")
                raise ValidationError(error_message)

        except Exception as e:
            payment.status = Payment.PaymentStatus.FAILED
            payment.save()
            raise ValidationError(f"An unexpected error occurred during verification: {str(e)}")

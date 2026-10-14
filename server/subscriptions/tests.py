from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from subscriptions.models import Payment, Plan, UserSubscription
from subscriptions.services import SubscriptionService

User = get_user_model()


@pytest.fixture
def user():
    # The post_save signal gives every new user a FREE subscription.
    return User.objects.create_user(email="payer@example.com", password="password123")


@pytest.fixture
def pro_plan():
    return Plan.objects.get(name=Plan.PlanType.PRO)


@pytest.fixture
def zarinpal():
    with patch("subscriptions.services.get_zarinpal") as factory:
        yield factory.return_value


@pytest.mark.django_db
class TestPaymentVerification:

    def test_successful_payment_moves_the_existing_subscription_to_the_plan(self, user, pro_plan, zarinpal):
        Payment.objects.create(user=user, plan=pro_plan, amount=pro_plan.price, authority="A1", status=Payment.Status.PENDING)
        zarinpal.verifications.verify.return_value = {"status": 100, "data": {"ref_id": 42, "fee": 0}}

        result = SubscriptionService.verify_zarinpal_payment(authority="A1", status="OK")

        assert result["ref_id"] == "42"
        assert UserSubscription.objects.filter(user=user).count() == 1
        sub = UserSubscription.objects.get(user=user)
        assert sub.plan == pro_plan
        assert sub.is_active
        assert sub.end_date > timezone.now() + timedelta(days=29)
        assert Payment.objects.get(authority="A1").status == Payment.Status.SUCCESS


@pytest.mark.django_db
class TestPaymentInitiation:

    def test_request_sends_no_sample_customer_data(self, user, pro_plan, zarinpal):
        zarinpal.payments.create.return_value = {"data": {"authority": "A2"}}
        zarinpal.payments.generate_payment_url.return_value = "https://pay.example/A2"
        client = APIClient()
        client.force_authenticate(user)

        response = client.post("/api/subscriptions/payment/initiate/", {"plan_id": pro_plan.id}, format="json")

        assert response.status_code == 200
        sent = zarinpal.payments.create.call_args.args[0]
        assert set(sent) == {"amount", "callback_url", "description"}


@pytest.mark.django_db
class TestExpiredPlan:

    def test_expired_subscription_falls_back_to_the_free_plan(self, user, pro_plan):
        UserSubscription.objects.filter(user=user).update(plan=pro_plan, end_date=timezone.now() - timedelta(days=1))
        user.refresh_from_db()

        assert SubscriptionService.get_user_plan(user).name == Plan.PlanType.FREE


@pytest.mark.django_db
class TestPaymentReturnsToTheClient:

    def test_zarinpal_sends_the_user_to_the_client_result_page(self, user, pro_plan, zarinpal, settings):
        settings.CLIENT_URL = "https://app.example.com/"
        zarinpal.payments.create.return_value = {"data": {"authority": "A3"}}
        zarinpal.payments.generate_payment_url.return_value = "https://pay.example/A3"
        client = APIClient()
        client.force_authenticate(user)

        client.post("/api/subscriptions/payment/initiate/", {"plan_id": pro_plan.id}, format="json")

        assert zarinpal.payments.create.call_args.args[0]["callback_url"] == "https://app.example.com/payment/result"

    def test_verifying_twice_reports_the_first_success(self, user, pro_plan, zarinpal):
        Payment.objects.create(user=user, plan=pro_plan, amount=pro_plan.price, authority="A4", status=Payment.Status.PENDING)
        zarinpal.verifications.verify.return_value = {"status": 100, "data": {"ref_id": 77, "fee": 0}}
        client = APIClient()
        url = "/api/subscriptions/payment/verify/?Authority=A4&Status=OK"

        first = client.get(url)
        second = client.get(url)  # the user reloads the result page

        assert first.status_code == second.status_code == 200
        assert second.json() == {"message": "Payment successful. Subscription updated.", "ref_id": "77", "plan": "PRO"}
        assert zarinpal.verifications.verify.call_count == 1

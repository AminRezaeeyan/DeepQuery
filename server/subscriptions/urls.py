from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, MySubscriptionView, PaymentView, PaymentVerifyView

router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
    path('my-subscription/', MySubscriptionView.as_view(), name='my-subscription'),
    path('payment/initiate/', PaymentView.as_view(), name='payment-initiate'),
    path('payment/verify/', PaymentVerifyView.as_view(), name='payment-verify'),
]

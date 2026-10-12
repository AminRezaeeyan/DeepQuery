from rest_framework import viewsets, views, mixins, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Plan
from .serializers import PaymentInitiateSerializer, PaymentVerifySerializer, PlanSerializer, UserSubscriptionSerializer
from .services import SubscriptionService

class PlanViewSet(mixins.ListModelMixin,mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # Prices are public.
    permission_classes = [AllowAny]
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class MySubscriptionView(generics.RetrieveAPIView):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.subscription


class PaymentView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = serializer.validated_data["plan_id"]

        payment_info = SubscriptionService.initiate_zarinpal_payment(
            user=request.user,
            plan=plan,
            request=request
        )

        return Response(payment_info)



class PaymentVerifyView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = PaymentVerifySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        authority = serializer.validated_data["Authority"]
        status_param = serializer.validated_data["Status"]

        result = SubscriptionService.verify_zarinpal_payment(
            authority=authority,
            status=status_param
        )

        return Response(result)


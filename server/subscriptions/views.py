from django.forms import ValidationError
from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Plan, Payment
from .serializers import PlanSerializer
from .services import SubscriptionService

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

class MySubscriptionView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = SubscriptionService.get_user_plan(request.user)
        return Response({
            "current_plan": plan.name,
            "daily_message_limit": plan.daily_message_limit,
            "daily_document_limit": plan.daily_document_limit,
        })

class PaymentView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"error": "plan_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id)
            service = SubscriptionService()
            payment_info = service.initiate_zarinpal_payment(request.user, plan, request)
            return Response(payment_info, status=status.HTTP_200_OK)
        except Plan.DoesNotExist:
            return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)


class PaymentVerifyView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        authority = request.query_params.get('Authority')
        zarinpal_status = request.query_params.get('Status')

        if not authority or not zarinpal_status:
            return Response({"error": "Missing Authority or Status from callback."}, status=status.HTTP_400_BAD_REQUEST)

        service = SubscriptionService()
        try:
            result = service.verify_zarinpal_payment(authority=authority, status=zarinpal_status)
            return Response(result, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)

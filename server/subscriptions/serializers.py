from rest_framework import serializers
from .models import Plan, UserSubscription

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'price', 'daily_message_limit', 'daily_document_limit', 'daily_image_limit']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'plan', 'start_date', 'end_date', 'is_active']

class PaymentInitiateSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()

    def validate_plan_id(self, value):
        try:
            plan = Plan.objects.get(id=value)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan not found.")
        return plan

class PaymentVerifySerializer(serializers.Serializer):
    Authority = serializers.CharField()
    Status = serializers.CharField()

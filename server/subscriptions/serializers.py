# subscriptions/serializers.py
from rest_framework import serializers
from .models import Plan, UserSubscription, Payment

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'price', 'daily_message_limit', 'daily_document_limit']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'plan', 'start_date', 'end_date', 'is_active']

class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'plan_name', 'amount', 'authority', 'status', 'created_at']
        read_only_fields = ['amount', 'authority', 'status', 'created_at']

from rest_framework import serializers
from .models import LLMProvider


class ModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = LLMProvider
        fields = [
            "id",
            "name",
            "provider_type",
            "model_name",
            "is_default",
        ]

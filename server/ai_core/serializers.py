from rest_framework import serializers
from .models import LLMProvider


class ModelSerializer(serializers.ModelSerializer):
    is_default_for_chat = serializers.SerializerMethodField()

    class Meta:
        model = LLMProvider
        fields = [
            "id",
            "name",
            "provider_type",
            "model_name",
            "is_default_for_chat",
        ]

    def get_is_default_for_chat(self, obj):
        for config in obj.task_configs.all():
            if config.task_type == "chat" and config.is_default_for_chat:
                return True
        return False

from rest_framework import serializers
from .models import Chat, Message

from  ai_core.exceptions import ProviderUnavailable
from ai_core.services.provider_service import ProviderService


class AnswerOptionsSerializer(serializers.Serializer):
    """Per-request answer settings, accepted when sending or editing a message."""
    enable_web_search = serializers.BooleanField(write_only=True, required=False, default=False)
    strict_quote_mode = serializers.BooleanField(write_only=True, required=False, default=False)
    challenge_mode = serializers.BooleanField(write_only=True, required=False, default=False)
    audience_type = serializers.CharField(write_only=True, required=False, default="General")
    reasoning_depth = serializers.CharField(write_only=True, required=False, default="Medium")

    OPTION_FIELDS = ["enable_web_search", "strict_quote_mode", "challenge_mode", "audience_type", "reasoning_depth"]

    def answer_options(self):
        return {name: self.validated_data[name] for name in self.OPTION_FIELDS}

    def create(self, validated_data):
        for name in self.OPTION_FIELDS:
            validated_data.pop(name, None)
        return super().create(validated_data)


class MessageSerializer(AnswerOptionsSerializer, serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = [
            'uuid', 'role', 'content', 'image', 'enable_web_search', 
            'strict_quote_mode', 'challenge_mode', 'audience_type', 
            'reasoning_depth', 'created_at'
        ]
        read_only_fields = ['uuid', 'role', 'created_at']



class MessageUpdateSerializer(AnswerOptionsSerializer, serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = ["content", *AnswerOptionsSerializer.OPTION_FIELDS]

    def validate(self, data):
        message = self.instance

        if message.role != Message.Role.USER:
            raise serializers.ValidationError("Only user messages can be edited.")

        last_user = (
            message.chat.messages
            .filter(role=Message.Role.USER, is_deleted=False)
            .order_by("-created_at")
            .first()
        )

        if last_user != message:
            raise serializers.ValidationError("Only the last user message can be edited.")

        return data


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['uuid', 'provider_id', 'title', 'is_temporary', 'created_at', 'updated_at']
        read_only_fields = fields


    
class ChatUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ["title", "provider_id", "is_temporary"]

    def validate(self, data):
        chat = self.instance

        if "is_temporary" in data:
            new_value = data["is_temporary"]

            if new_value != chat.is_temporary:
                if Message.objects.filter(chat=chat).exists():
                    raise serializers.ValidationError(
                        "Temporary mode can only be changed when chat has no messages."
                    )

        return data

    def validate_provider_id(self, value):
        chat = self.instance

        if value == chat.provider_id:
            return value

        if Message.objects.filter(chat=chat).exists():
            raise serializers.ValidationError(
                "Provider cannot be changed once the chat has messages."
            )

        try:
            ProviderService.validate_chat_provider_id(value)
        except ProviderUnavailable as e:
            raise serializers.ValidationError(str(e))

        return value


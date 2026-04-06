from rest_framework import serializers
from .models import Chat, Message

from  ai_core.exceptions import ProviderUnavailable
from ai_core.services.provider_service import ProviderService


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['uuid', 'role', 'content', 'created_at']
        read_only_fields = ['uuid', 'role','created_at']


class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['content']

    def validate(self, attrs):
        message = self.instance
        if message.role != Message.Role.USER:
            raise serializers.ValidationError("Only user messages can be edited.")
        last_user_msg = (
            Message.objects.filter(chat=message.chat, role=Message.Role.USER)
            .order_by("-created_at")
            .first()
        )
        if message != last_user_msg:
            raise serializers.ValidationError("Only the last user message can be edited.")
        return attrs


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['uuid', 'provider_id', 'title', 'created_at']
        read_only_fields = fields


    
class ChatUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ["title", "provider_id"]

    def validate_provider_id(self, value):
        chat = self.instance

        # provider unchanged
        if value == chat.provider_id:
            return value

        # check if chat already has messages
        if Message.objects.filter(chat=chat).exists():
            raise serializers.ValidationError(
                "Provider cannot be changed once the chat has messages."
            )
        
        # Validate provider existence/activeness
        try:
            ProviderService.validate_provider_id(value)
        except ProviderUnavailable as e:
            raise serializers.ValidationError(str(e))

        return value

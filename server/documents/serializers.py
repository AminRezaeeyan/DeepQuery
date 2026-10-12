from rest_framework import serializers
from .models import Document
from .services.document_processing_service import DocumentProcessingService
import os

from django.conf import settings

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["uuid", "chat", "file", "original_filename", "status", "created_at"]
        read_only_fields = ["uuid", "original_filename", "status", "created_at"]

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in DocumentProcessingService.SUPPORTED_EXTENSIONS:
            raise serializers.ValidationError(f"Unsupported file type. Supported: {', '.join(DocumentProcessingService.SUPPORTED_EXTENSIONS)}")
        if value.size > settings.DOCUMENT_MAX_UPLOAD_BYTES:
            limit_mb = settings.DOCUMENT_MAX_UPLOAD_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f"Files can be at most {limit_mb} MB.")
        if not DocumentProcessingService.content_matches_extension(value):
            raise serializers.ValidationError(f"The file's content doesn't match its {ext} extension.")
        return value

    def validate_chat(self, chat):
        request = self.context["request"]
        if chat.user_id != request.user.id or chat.is_deleted:
            # Same message as a missing chat, so other users' chat ids don't leak.
            raise serializers.ValidationError("Chat not found.")
        return chat

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['original_filename'] = validated_data['file'].name
        return super().create(validated_data)

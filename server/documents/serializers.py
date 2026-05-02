from rest_framework import serializers
from .models import Document
from .services.document_processing_service import DocumentProcessingService
import os

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["uuid", "chat", "file", "original_filename", "status", "created_at"]
        read_only_fields = ["uuid", "original_filename", "status", "created_at"]

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in DocumentProcessingService.SUPPORTED_EXTENSIONS:
            raise serializers.ValidationError(f"Unsupported file type. Supported: {', '.join(DocumentProcessingService.SUPPORTED_EXTENSIONS)}")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['original_filename'] = validated_data['file'].name
        return super().create(validated_data)

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import Document
from .serializers import DocumentSerializer
from .tasks import extract_and_index_document


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "delete"]
    lookup_field = "uuid"

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        doc = serializer.save()
        extract_and_index_document.delay(doc.id)

    @action(detail=True, methods=["get"])
    def download(self, request, uuid=None):
        doc = get_object_or_404(
            Document, uuid=uuid, user=request.user
        )
        return Response(
            {
                "id": str(doc.uuid),
                "original_filename": doc.original_filename,
                "status": doc.status,
            }
        )

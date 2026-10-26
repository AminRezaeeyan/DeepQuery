from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from .models import Document
from .serializers import DocumentSerializer
from .tasks import extract_and_index_document

from subscriptions.services import SubscriptionService, SubscriptionLimitExceeded


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "delete"]
    lookup_field = "uuid"

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        try:
            SubscriptionService.consume(self.request.user, "document")
        except SubscriptionLimitExceeded as e:
            raise ValidationError(str(e))

        try:
            doc = serializer.save()
        except Exception:
            SubscriptionService.refund(self.request.user, "document")
            raise

        extract_and_index_document.delay(doc.id)

from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import Chat, Message
from .serializers import (
    ChatSerializer,
    ChatUpdateSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)


class ChatViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return ChatUpdateSerializer
        return ChatSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get", "post"])
    def messages(self, request, uuid=None):
        chat = self.get_object()

        if request.method == "GET":
            messages = chat.messages.order_by("-created_at")
            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = MessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(chat=chat)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_queryset(self):
        return Message.objects.filter(chat__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return MessageUpdateSerializer
        return MessageSerializer

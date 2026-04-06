from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.http import StreamingHttpResponse
from ai_core.services.chat_service import ChatService
from ai_core.services.provider_service import ProviderService
from ai_core.exceptions import ProviderUnavailable

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
        serializer.save(user=self.request.user, provider_id=ProviderService.get_default_provider_id())

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

            # 1 - Save user message
            user_message = serializer.save(
                chat=chat,
                role=Message.Role.USER
            )

            try:
                chat_service = ChatService(chat.provider_id)
            except ProviderUnavailable as e:
                raise ValidationError(str(e))

            # 2 - Stream assistant answer
            def stream():
                assistant_text = ""

                for token in chat_service.stream_answer(user_message.content):
                    assistant_text += token
                    yield token

                # 3 - Save assistant message after stream completes
                Message.objects.create(
                    chat=chat,
                    role=Message.Role.ASSISTANT,
                    content=assistant_text
                )

            return StreamingHttpResponse(
                stream(),
                content_type="text/plain"
            )
    

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

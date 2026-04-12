from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.http import StreamingHttpResponse

from ai_core.services.chat_service import ChatGenerationService
from ai_core.services.provider_service import ProviderService
from ai_core.exceptions import ProviderUnavailable, ContextLimitExceededError
from chats.services.chat_service import ChatService
from chats.pagination import ChatCursorPagination, MessageCursorPagination

from .models import Chat, Message
from .serializers import (
    ChatSerializer,
    ChatUpdateSerializer,
    MessageSerializer,
    MessageUpdateSerializer,
)


class ChatViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    pagination_class = ChatCursorPagination

    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return ChatUpdateSerializer
        return ChatSerializer

    def perform_create(self, serializer):
        provider_id = ProviderService.get_default_chat_provider_id()

        chat = ChatService.get_or_create_chat(
            user=self.request.user,
            provider_id=provider_id
        )

        serializer.instance = chat

    def perform_destroy(self, instance):
        instance.mark_deleted()


    @action(detail=True, methods=["get", "post"])
    def messages(self, request, uuid=None):
        chat = self.get_object()

        if request.method == "GET":
            queryset = chat.messages.order_by("-created_at")

            paginator = MessageCursorPagination()
            page = paginator.paginate_queryset(queryset, request)

            serializer = MessageSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        elif request.method == "POST":

            serializer = MessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            if chat.is_deleted:
                raise ValidationError("Chat has been deleted.")


            user_message = serializer.save(
                chat=chat,
                role=Message.Role.USER
            )

            try:
                stream = ChatService.generate_stream(chat, user_message)
            except ProviderUnavailable as e:
                raise ValidationError(str(e))
            except ContextLimitExceededError as e:
                raise ValidationError(str(e))

            return StreamingHttpResponse(
                stream,
                content_type="text/plain"
            )
    

class MessageViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    http_method_names = ["get", "post", "patch"]
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_queryset(self):
        return Message.objects.filter(chat__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return MessageUpdateSerializer
        return MessageSerializer

    def update(self, request, *args, **kwargs):
        message = self.get_object()

        serializer = self.get_serializer(data=request.data, instance=message, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            stream = ChatService.edit_user_message(
                message,
                serializer.validated_data["content"]
            )
        except ProviderUnavailable as e:
            raise ValidationError(str(e))

        return StreamingHttpResponse(
            stream,
            content_type="text/plain"
        )


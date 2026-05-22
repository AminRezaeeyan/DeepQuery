from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.http import StreamingHttpResponse
from django.db.models import Q

from ai_core.services.chat_service import ChatTitleGenerator
from ai_core.services.provider_service import ProviderService
from ai_core.exceptions import ProviderUnavailable, ContextLimitExceededError
from chats.services.chat_service import ChatService
from chats.pagination import ChatCursorPagination, MessageCursorPagination

from subscriptions.services import SubscriptionService, SubscriptionLimitExceeded

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

    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q","").strip()

        if not query:
            return Response({"detail": "Query 'q' is required."}, status=400)
        
        chats = (
            Chat.objects
            .filter(user=request.user)
            .filter(
                Q(title__icontains=query) |
                Q(messages__content__icontains=query)
            )
            .distinct()
            .order_by("-updated_at")
        )

        serializer = ChatSerializer(chats, many=True)
        return Response(serializer.data)


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

            data = serializer.validated_data
            image = data.get("image")
            enable_web_search = data.get("enable_web_search", False)
            strict_quote_mode = data.get("strict_quote_mode", False)
            audience_type = data.get("audience_type", "General")
            reasoning_depth = data.get("reasoning_depth", "Medium")
            challenge_mode = data.get("challenge_mode", False)

            try:
                SubscriptionService.check_message_limit(request.user)
                if image:
                    SubscriptionService.check_image_limit(request.user)
            except SubscriptionLimitExceeded as e:
                raise ValidationError(str(e))


            if chat.is_deleted:
                raise ValidationError("Chat has been deleted.")


            user_message = serializer.save(
                chat=chat,
                role=Message.Role.USER
            )

            is_first_message = chat.messages.exclude(id=user_message.id).count() == 0

            if is_first_message:
                from .tasks import generate_chat_title
                generate_chat_title.delay(chat.id, user_message.id)

            try:
                stream = ChatService.generate_stream(chat, user_message, enable_web_search=enable_web_search, strict_quote_mode=strict_quote_mode, audience_type=audience_type, reasoning_depth=reasoning_depth, challenge_mode=challenge_mode)

            except ProviderUnavailable as e:
                raise ValidationError(str(e))
            except ContextLimitExceededError as e:
                raise ValidationError(str(e))

            SubscriptionService.increment_usage(request.user, "message")
            if image:
                SubscriptionService.increment_usage(request.user, "image")

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

        try:
            SubscriptionService.check_message_limit(request.user)
        except SubscriptionLimitExceeded as e:
            raise ValidationError(str(e))

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


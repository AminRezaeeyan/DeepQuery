from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
import mimetypes

from django.http import FileResponse, Http404, StreamingHttpResponse
from django.db.models import Q

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


def charge(user, resources):
    """
    Counts each resource against the user's daily limits and returns a
    function that refunds them all, for requests that don't complete.
    """
    charged = []
    try:
        for resource in resources:
            SubscriptionService.consume(user, resource)
            charged.append(resource)
    except SubscriptionLimitExceeded as e:
        for resource in charged:
            SubscriptionService.refund(user, resource)
        raise ValidationError(str(e))

    def refund():
        for resource in charged:
            SubscriptionService.refund(user, resource)
        charged.clear()

    return refund


class ChatViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    pagination_class = ChatCursorPagination

    def get_queryset(self):
        queryset = Chat.objects.filter(user=self.request.user)
        # Temporary chats stay reachable by id while open, but never show up in history.
        if self.action == "list":
            queryset = queryset.filter(is_temporary=False)
        return queryset

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
            .filter(user=request.user, is_temporary=False)
            .filter(
                Q(title__icontains=query) |
                # Both conditions in one Q so they apply to the same message.
                Q(messages__content__icontains=query, messages__is_deleted=False)
            )
            .distinct()
        )

        paginator = ChatCursorPagination()
        page = paginator.paginate_queryset(chats, request)
        serializer = ChatSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


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

            image = serializer.validated_data.get("image")
            options = serializer.answer_options()

            if chat.is_deleted:
                raise ValidationError("Chat has been deleted.")

            refund = charge(request.user, ["message", "image"] if image else ["message"])

            try:
                user_message = serializer.save(
                    chat=chat,
                    role=Message.Role.USER
                )

                is_first_message = chat.messages.exclude(id=user_message.id).count() == 0

                if is_first_message:
                    from .tasks import generate_chat_title
                    generate_chat_title.delay(chat.id, user_message.id)

                stream = ChatService.generate_stream(chat, user_message, on_incomplete=refund, **options)

            except (ProviderUnavailable, ContextLimitExceededError) as e:
                refund()
                raise ValidationError(str(e))
            except Exception:
                refund()
                raise

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

    @action(detail=True, methods=["get"])
    def image(self, request, uuid=None):
        # Chat images are private, so they're served here (owner only)
        # rather than from a public media URL.
        message = self.get_object()
        if not message.image:
            raise Http404
        content_type = mimetypes.guess_type(message.image.name)[0] or "application/octet-stream"
        return FileResponse(message.image.open("rb"), content_type=content_type)

    def update(self, request, *args, **kwargs):
        message = self.get_object()

        serializer = self.get_serializer(data=request.data, instance=message, partial=True)
        serializer.is_valid(raise_exception=True)

        refund = charge(request.user, ["message"])

        try:
            stream = ChatService.edit_user_message(
                message,
                serializer.validated_data["content"],
                on_incomplete=refund,
                **serializer.answer_options(),
            )
        except (ProviderUnavailable, ContextLimitExceededError) as e:
            refund()
            raise ValidationError(str(e))
        except Exception:
            refund()
            raise

        return StreamingHttpResponse(
            stream,
            content_type="text/plain"
        )


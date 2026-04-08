from django.db.models import Count
from chats.models import Chat, Message
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.chat_service import ChatGenerationService


class ChatService:

    @staticmethod
    def get_or_create_chat(user, provider_id):
        chat = (
            Chat.objects
            .filter(user=user)
            .annotate(message_count=Count("messages"))
            .filter(message_count=0)
            .first()
        )

        if chat:
            return chat

        return Chat.objects.create(
            user=user,
            provider_id=provider_id,
        )
    
    @staticmethod
    def generate_stream(chat, user_message):
 
        try:
            chat_service = ChatGenerationService(chat.provider_id)
        except ProviderUnavailable:
            raise
                
        def stream():
            assistant_text = ""

            for token in chat_service.stream_answer(user_message.content):
                assistant_text += token
                yield token

            Message.objects.create(
                chat=chat,
                role=Message.Role.ASSISTANT,
                content=assistant_text
            )

        chat.mark_updated()
        return stream()
    
    @staticmethod
    def edit_user_message(old_message, new_content):
        chat = old_message.chat

        # 1. Mark old user message deleted
        old_message.mark_edited()

        # 2. Soft delete assistant reply originally answering the old message
        assistant = (
            Message.objects
            .filter(
                chat=chat,
                role=Message.Role.ASSISTANT,
                created_at__gt=old_message.created_at
            )
            .order_by("created_at")
            .first()
        )

        if assistant:
            assistant.mark_deleted()

        # 3. Create new user message
        new_user_message = Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content=new_content
        )

        return ChatService.generate_stream(chat, new_user_message)
    
    @staticmethod
    def get_message_pairs(chat_id, page=1, page_size=20):
        offset = (page - 1) * page_size

        qs = (
            Message.objects
            .filter(chat_id=chat_id)
            .order_by("-created_at")
            .values("role", "content")[offset:offset + page_size]
        )

        return list(qs)

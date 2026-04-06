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

        return stream()

    @staticmethod
    def regenerate_from_edit(message):
        """
        Used when user edits their last message.
        Deletes assistant reply and regenerates.
        """

        chat = message.chat

        assistant = (
            Message.objects
            .filter(
                chat=chat,
                role=Message.Role.ASSISTANT,
                created_at__gt=message.created_at
            )
            .order_by("created_at")
            .first()
        )

        if assistant:
            assistant.delete()

        return ChatService.generate_stream(chat, message)

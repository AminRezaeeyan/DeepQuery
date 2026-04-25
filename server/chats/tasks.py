from celery import shared_task
from django.db import transaction

from chats.models import Chat, Message
from ai_core.services.chat_service import ChatTitleGenerator
from ai_core.exceptions import ProviderUnavailable

@shared_task
def generate_chat_title(chat_id: int, first_message_id: int):
    try:
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist:
        return

    if chat.title != 'New chat':
        return

    try:
        first_message = Message.objects.get(id=first_message_id)
    except Message.DoesNotExist:
        return

    if first_message.chat_id != chat.id:
        return

    try:
        generator = ChatTitleGenerator()
        title = generator.generate(first_message.content)
    except ProviderUnavailable:
        return

    if not title:
        return

    with transaction.atomic():
        chat.title = title
        chat.save(update_fields=["title", "updated_at"])

import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

from chats.models import Message
from chats.services.chat_service import ChatService


@pytest.mark.django_db
class TestImagesReachTheModel:

    @pytest.fixture(autouse=True)
    def media_root(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    def _run(self, message):
        with patch("chats.services.chat_service.ChatGenerationService") as service_cls:
            service_cls.return_value.stream_answer.return_value = iter(["ok"])
            list(ChatService.generate_stream(message.chat, message))
        return service_cls.return_value.stream_answer.call_args

    def test_image_bytes_and_type_are_passed_to_the_model(self, chat):
        message = Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content="What is in this picture?",
            image=SimpleUploadedFile("photo.png", b"png-bytes", content_type="image/png"),
        )

        call = self._run(message)

        assert call.args == ("What is in this picture?",)
        assert call.kwargs == {"image_bytes": b"png-bytes", "mime_type": "image/png"}

    def test_text_only_message_sends_no_image(self, chat):
        message = Message.objects.create(chat=chat, role=Message.Role.USER, content="Hi")

        call = self._run(message)

        assert call.kwargs == {"image_bytes": None, "mime_type": None}

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
            service_cls.return_value.stream_prepared.return_value = iter(["ok"])
            list(ChatService.generate_stream(message.chat, message))
        return service_cls.return_value.stream_prepared.call_args

    def test_image_bytes_and_type_are_passed_to_the_model(self, chat):
        message = Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content="What is in this picture?",
            image=SimpleUploadedFile("photo.png", b"png-bytes", content_type="image/png"),
        )

        call = self._run(message)

        assert call.kwargs["image_bytes"] == b"png-bytes"
        assert call.kwargs["mime_type"] == "image/png"

    def test_text_only_message_sends_no_image(self, chat):
        message = Message.objects.create(chat=chat, role=Message.Role.USER, content="Hi")

        call = self._run(message)

        assert call.kwargs["image_bytes"] is None
        assert call.kwargs["mime_type"] is None


@pytest.mark.django_db
class TestImageUploadLimits:

    @pytest.fixture(autouse=True)
    def media_root(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    def png(self):
        import io
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "green").save(buffer, format="PNG")
        return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")

    def test_rejects_images_over_the_size_limit(self, auth_client, chat, settings):
        settings.CHAT_IMAGE_MAX_UPLOAD_BYTES = 10

        with patch("chats.services.chat_service.ChatGenerationService") as service_cls:
            response = auth_client.post(f"/api/chats/{chat.uuid}/messages/", {"content": "q", "image": self.png()}, format="multipart")

        assert response.status_code == 400
        service_cls.assert_not_called()

    def test_rejects_files_that_are_not_images(self, auth_client, chat):
        fake = SimpleUploadedFile("photo.png", b"#!/bin/sh\necho hi", content_type="image/png")

        response = auth_client.post(f"/api/chats/{chat.uuid}/messages/", {"content": "q", "image": fake}, format="multipart")

        assert response.status_code == 400

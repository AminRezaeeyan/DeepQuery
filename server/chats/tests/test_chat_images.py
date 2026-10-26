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
            service_cls.return_value.answer_events.return_value = iter([{"type": "text", "text": "ok"}])
            list(ChatService.generate_stream(message.chat, message))
        return service_cls.return_value.answer_events.call_args

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


@pytest.mark.django_db
class TestServingChatImages:

    @pytest.fixture(autouse=True)
    def media_root(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    @pytest.fixture
    def message(self, chat):
        return Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content="What is this?",
            image=SimpleUploadedFile("photo.png", b"png-bytes", content_type="image/png"),
        )

    def test_message_lists_point_at_a_working_image_url(self, auth_client, chat, message):
        listed = auth_client.get(f"/api/chats/{chat.uuid}/messages/").json()["results"][0]

        response = auth_client.get(listed["image"])

        assert listed["image"] == f"/api/messages/{message.uuid}/image/"
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert b"".join(response.streaming_content) == b"png-bytes"

    def test_other_users_cannot_fetch_the_image(self, api_client, other_user, message):
        api_client.force_authenticate(other_user)

        assert api_client.get(f"/api/messages/{message.uuid}/image/").status_code == 404

    def test_messages_without_an_image_have_no_url(self, auth_client, chat):
        Message.objects.create(chat=chat, role=Message.Role.USER, content="text only")

        assert auth_client.get(f"/api/chats/{chat.uuid}/messages/").json()["results"][0]["image"] is None

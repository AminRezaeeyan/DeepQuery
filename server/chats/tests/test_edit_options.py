import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

from chats.models import Message


@pytest.mark.django_db
class TestEditKeepsTheRequest:

    @pytest.fixture(autouse=True)
    def media_root(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    def test_edit_passes_answer_options_and_keeps_the_image(self, auth_client, chat):
        question = Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content="old question",
            image=SimpleUploadedFile("chart.png", b"png", content_type="image/png"),
        )
        Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="old answer")

        with patch("chats.services.chat_service.ChatGenerationService") as service_cls:
            service_cls.return_value.stream_prepared.return_value = iter(["new answer"])
            response = auth_client.patch(
                f"/api/messages/{question.uuid}/",
                {
                    "content": "new question",
                    "enable_web_search": True,
                    "strict_quote_mode": True,
                    "challenge_mode": True,
                    "audience_type": "Expert",
                    "reasoning_depth": "High",
                },
                format="json",
            )
            b"".join(response.streaming_content)

        options = service_cls.call_args.kwargs
        assert options["enable_web_search"] is True
        assert options["strict_quote_mode"] is True
        assert options["challenge_mode"] is True
        assert options["audience_type"] == "Expert"
        assert options["reasoning_depth"] == "High"

        edited = Message.objects.get(chat=chat, role=Message.Role.USER)
        assert edited.content == "new question"
        assert edited.image.name == question.image.name

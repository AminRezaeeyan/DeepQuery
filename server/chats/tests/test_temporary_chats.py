import pytest
from unittest.mock import patch
from rest_framework import status

from chats.models import Chat, Message
from ai_core.services.memory.long_term_memory import LongTermMemoryService


@pytest.mark.django_db
class TestTemporaryChatsStayOutOfHistory:

    @pytest.fixture
    def chats(self, user):
        normal = Chat.objects.create(user=user, title="Normal research")
        temporary = Chat.objects.create(user=user, title="Temporary research", is_temporary=True)
        Message.objects.create(chat=temporary, role=Message.Role.USER, content="secret research")
        return normal, temporary

    def test_list_hides_temporary_chats(self, auth_client, chats):
        response = auth_client.get("/api/chats/")

        assert response.status_code == status.HTTP_200_OK
        assert [c["title"] for c in response.data["results"]] == ["Normal research"]

    def test_search_hides_temporary_chats(self, auth_client, chats):
        response = auth_client.get("/api/chats/search/?q=research")

        assert [c["title"] for c in response.data] == ["Normal research"]

    def test_open_temporary_chat_is_still_reachable_by_id(self, auth_client, chats):
        _, temporary = chats

        assert auth_client.get(f"/api/chats/{temporary.uuid}/").status_code == status.HTTP_200_OK
        assert auth_client.get(f"/api/chats/{temporary.uuid}/messages/").status_code == status.HTTP_200_OK


class TestDisabledMemory:

    @pytest.fixture
    def memory(self):
        with patch("ai_core.services.memory.long_term_memory.EmbeddingService") as embedder:
            yield LongTermMemoryService(user_id=1, enabled=False), embedder.return_value

    def test_disabled_memory_is_never_read(self, memory):
        service, embedder = memory

        assert service.build_memory_context("query", token_limit=500) == ""
        embedder.search.assert_not_called()

    def test_disabled_memory_is_never_written(self, memory):
        service, _ = memory

        with patch("ai_core.services.memory.long_term_memory.extract_and_embed_facts_task") as task:
            service.store_from_message(chat_id=1, text="I live in Tehran")

        task.delay.assert_not_called()

import pytest

from chats.models import Chat, Message


@pytest.mark.django_db
class TestChatSearch:

    def search(self, client, q, url=None):
        return client.get(url or "/api/chats/search/", {"q": q} if not url else None).json()

    def test_deleted_messages_do_not_match(self, auth_client, user):
        chat = Chat.objects.create(user=user, title="Energy notes")
        message = Message.objects.create(chat=chat, role=Message.Role.USER, content="secret phrase")
        message.mark_deleted()

        assert self.search(auth_client, "secret phrase")["results"] == []

    def test_live_messages_still_match(self, auth_client, user):
        chat = Chat.objects.create(user=user, title="Energy notes")
        Message.objects.create(chat=chat, role=Message.Role.USER, content="solar panels in winter")

        assert [c["title"] for c in self.search(auth_client, "solar")["results"]] == ["Energy notes"]

    def test_results_are_paginated(self, auth_client, user):
        for i in range(25):
            Chat.objects.create(user=user, title=f"Solar study {i}")

        first = self.search(auth_client, "solar")
        second = self.search(auth_client, "solar", url=first["next"])

        assert len(first["results"]) == 20
        assert len(second["results"]) == 5
        assert second["next"] is None

import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddedObject, EmbeddingChunk, EmbeddingProvider, MemoryFact
from ai_core.services.embedding_service import EmbeddingService
from ai_core.tasks import finish_provider_switch, reembed_all_objects


@pytest.fixture(autouse=True)
def fake_openai_embeddings():
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5):
        yield


def make_provider(name, **flags):
    return EmbeddingProvider.objects.create(
        name=name, provider_type="openai", api_key="k", model_name=name, dimension=3, max_tokens=512, **flags
    )


@pytest.fixture
def providers():
    # The first provider becomes active and serving automatically.
    old = make_provider("old-model")
    new = make_provider("new-model", is_active=True)
    old.refresh_from_db()
    return old, new


@pytest.fixture
def fact(providers):
    old, _ = providers
    user = get_user_model().objects.create_user(email="mem@example.com", password="password123")
    fact = MemoryFact.objects.create(user_id=user.id, chat_id=1, fact="The user lives in Tehran")
    EmbeddingService(provider_id=old.id).embed_instance(fact, fact.fact, tag=f"user:{user.id}")
    return fact


@pytest.mark.django_db
class TestFinishProviderSwitch:

    def test_new_provider_takes_over_serving(self, providers):
        old, new = providers

        finish_provider_switch(new.id)

        old.refresh_from_db()
        new.refresh_from_db()
        assert new.is_serving and new.status == "ready"
        assert not old.is_serving


@pytest.mark.django_db
class TestReembedding:

    def test_reembeds_the_real_text_and_keeps_the_tag(self, providers, fact):
        _, new = providers

        reembed_all_objects(new.id)

        eo = EmbeddedObject.objects.get(provider=new, object_id=str(fact.pk))
        assert eo.tag == f"user:{fact.user_id}"
        assert [c.text for c in eo.chunks.all()] == ["The user lives in Tehran"]
        assert not EmbeddedObject.objects.exclude(provider=new).exists()


@pytest.mark.django_db
class TestSearchIsScopedToTheProvider:

    def test_search_ignores_chunks_from_another_provider(self, providers, fact):
        old, new = providers

        assert EmbeddingService(provider_id=new.id).search("Tehran", content_model=MemoryFact) == []
        assert len(EmbeddingService(provider_id=old.id).search("Tehran", content_model=MemoryFact)) == 1

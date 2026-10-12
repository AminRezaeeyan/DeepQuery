import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model

from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddingProvider, MemoryFact
from ai_core.services.embedding_service import EmbeddingService


@pytest.fixture
def service():
    EmbeddingProvider.objects.create(
        name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=512
    )
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5):
        yield EmbeddingService()


@pytest.fixture
def facts(service):
    user = get_user_model().objects.create_user(email="v@example.com", password="password123")
    facts = [MemoryFact.objects.create(user=user, fact=f"fact {i}") for i in range(5)]
    for fact in facts:
        service.embed_instance(fact, fact.fact, tag=f"user:{user.id}")
    return facts


@pytest.mark.django_db
class TestVectorSearch:

    def test_loads_results_in_a_fixed_number_of_queries(self, service, facts, django_assert_max_num_queries):
        service.search("fact", content_model=MemoryFact)  # warm the content-type cache

        with django_assert_max_num_queries(2):
            results = service.search("fact", content_model=MemoryFact, limit=5)

        assert {obj for obj, _, _ in results} == set(facts)

    def test_skips_results_whose_source_was_deleted(self, service, facts):
        MemoryFact.objects.filter(pk=facts[0].pk).delete()

        results = service.search("fact", content_model=MemoryFact, limit=5)

        assert facts[0] not in {obj for obj, _, _ in results}
        assert len(results) == 4

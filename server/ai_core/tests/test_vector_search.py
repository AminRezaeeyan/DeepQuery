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

        assert {obj for obj, _, _, _ in results} == set(facts)

    def test_skips_results_whose_source_was_deleted(self, service, facts):
        MemoryFact.objects.filter(pk=facts[0].pk).delete()

        results = service.search("fact", content_model=MemoryFact, limit=5)

        assert facts[0] not in {obj for obj, _, _, _ in results}
        assert len(results) == 4


def test_rare_words_outweigh_common_ones():
    from ai_core.services.embedding_service import bm25_rank
    texts = ["The dataset and the statistics of the dataset.", "The inter-annotator agreement of NEL is 94.61%.", "The dataset."]

    ranked = bm25_rank("NEL dataset inter-annotator agreement", texts)

    assert ranked[0][0] == 1


def test_persian_matches_across_arabic_letter_forms():
    from ai_core.services.embedding_service import bm25_rank

    # The query types the Arabic yeh and kaf; the passage uses the Persian letters.
    assert [i for i, _ in bm25_rank("كتابخانه ملي", ["کتابخانه ملی ایران", "موزه"])] == [0]


@pytest.mark.django_db
def test_hybrid_search_finds_an_exact_term_the_vectors_rank_low():
    EmbeddingProvider.objects.create(name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=512)
    user = get_user_model().objects.create_user(email="h@example.com", password="password123")
    target = "Each mention has 3.80 candidates; the inter-annotator agreement is 94.61%."
    texts = [f"Dataset statistics overview, part {i}." for i in range(8)] + [target]
    # The vectors put every distractor closer to the query than the passage that answers it.
    vector = lambda text: [0.0, 1.0, 0.0] if text == target else [1.0, 0.1, 0.0]
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda batch: [vector(t) for t in batch]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[1.0, 0.0, 0.0]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5):
        service = EmbeddingService()
        for text in texts:
            service.embed_instance(MemoryFact.objects.create(user=user, fact=text), text, tag="chat:1")

        by_vector = [text for _, _, text, _ in service.search("inter-annotator agreement", MemoryFact, limit=3, tag="chat:1")]
        hybrid = [text for _, _, text, _ in service.hybrid_search("inter-annotator agreement", MemoryFact, limit=3, tag="chat:1")]

    assert target not in by_vector
    assert hybrid[0] == target

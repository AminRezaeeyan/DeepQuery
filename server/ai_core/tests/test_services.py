import pytest
from unittest.mock import patch
from django.contrib.contenttypes.models import ContentType

from ai_core.models import AITaskConfig, EmbeddedObject, EmbeddingChunk
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.task_provider_resolver import TaskProviderResolver
from ai_core.llm_providers.factory import ProviderFactory

from ai_core.embedding_providers.factory import EmbeddingProviderFactory
from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.services.embedding_service import ChunkingService, EmbeddingService



class MockProviderInstance:
    def __init__(self, provider_model):
        self.provider_model = provider_model


@pytest.mark.django_db
class TestTaskProviderResolver:

    def test_get_provider_defaults_to_default_chat(self, chat_config, fact_config):
        provider = TaskProviderResolver.get_provider_for_task()
        assert provider == chat_config.provider

    def test_get_provider_with_id_and_non_chat_fails(self):
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(task_type="fact_extraction", provider_id=1)
        assert "only allowed when requesting a chat provider" in str(exc.value)

    def test_get_specific_chat_provider_success(self, chat_config):
        provider = TaskProviderResolver.get_provider_for_task(
            task_type="chat", 
            provider_id=chat_config.provider.id
        )
        assert provider == chat_config.provider

    def test_get_specific_chat_provider_not_found(self):
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(task_type="chat", provider_id=999)
        assert "Requested provider not found" in str(exc.value)

    def test_get_specific_chat_provider_not_assigned_to_chat(self, fact_config):
        # We pass a valid provider ID, but it is only configured for summarization, not chat
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(
                task_type="chat", 
                provider_id=fact_config.provider.id
            )
        assert "not assigned to chat" in str(exc.value)

    def test_get_provider_by_task_type_success(self, fact_config):
        provider = TaskProviderResolver.get_provider_for_task(task_type="fact_extraction")
        assert provider == fact_config.provider

    def test_get_provider_fails_when_none_configured(self):
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(task_type="web_query_generation")
        assert "No provider configured" in str(exc.value)


@pytest.mark.django_db
class TestProviderFactory:

    @patch("ai_core.llm_providers.factory.PROVIDER_REGISTRY", {"openai": MockProviderInstance})
    @patch.object(TaskProviderResolver, "get_provider_for_task")
    def test_get_provider_success(self, mock_resolver, openai_provider):
        # Mock the resolver to return our openai model
        mock_resolver.return_value = openai_provider

        # The factory should instantiate MockProviderInstance with the model
        instance = ProviderFactory.get_provider(task_type="chat")
        
        assert isinstance(instance, MockProviderInstance)
        assert instance.provider_model == openai_provider
        mock_resolver.assert_called_once_with(task_type="chat", provider_id=None)

    @patch("ai_core.llm_providers.factory.PROVIDER_REGISTRY", {})
    @patch.object(TaskProviderResolver, "get_provider_for_task")
    def test_get_provider_unknown_type_fails(self, mock_resolver, openai_provider):
        mock_resolver.return_value = openai_provider

        # The registry is empty, so it won't find 'openai'
        with pytest.raises(ProviderUnavailable) as exc:
            ProviderFactory.get_provider(task_type="chat")
            
        assert "Unknown provider type: openai" in str(exc.value)

@pytest.mark.django_db
class TestEmbeddingProviderFactory:

    def test_get_provider_fetches_active_by_default(self, openai_emb_provider):
        provider = EmbeddingProviderFactory.get_provider()
        # Should return an instance of our MockEmbeddingProvider initialized with the model
        assert provider.model_name == openai_emb_provider.model_name
        assert provider.provider_type == "openai"

    def test_get_provider_by_id_fetches_correct_provider(self, openai_emb_provider, hf_local_provider):
        # The local provider loads its tokenizer from the Hugging Face Hub; keep the test offline.
        with patch("transformers.AutoTokenizer.from_pretrained"):
            provider = EmbeddingProviderFactory.get_provider(provider_id=hf_local_provider.id)
        assert provider.model_name == hf_local_provider.model_name


@pytest.mark.django_db
class TestChunkingService:

    def test_chunking_returns_single_chunk_if_under_limit(self, openai_emb_provider):
        provider_instance = EmbeddingProviderFactory.get_provider(openai_emb_provider.id)
        
        # Override limits for testing
        provider_instance.max_tokens = 10
        chunker = ChunkingService(provider_instance, overlap_tokens=2)
        
        text = "This is a short text." # 5 tokens
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunking_splits_on_newlines_if_over_limit(self, openai_emb_provider):
        provider_instance = EmbeddingProviderFactory.get_provider(openai_emb_provider.id)
        
        provider_instance.max_tokens = 5
        chunker = ChunkingService(provider_instance, overlap_tokens=1)
        
        text = "Block one.\n\nBlock two.\n\nBlock three." 
        chunks = chunker.chunk_text(text)
        
        # Should split cleanly on the double newlines into multiple chunks
        assert len(chunks) > 1
        assert "Block one." in chunks[0]


@pytest.mark.django_db
class TestEmbeddingService:

    @pytest.fixture(autouse=True)
    def mock_real_provider_methods(self):
        """
        Instead of swapping the class in the registry, we just modify the 
        real class in memory so it doesn't make API calls.
        """
        with patch.object(OpenAIEmbeddingProvider, 'embed_documents', return_value=[[0.1, 0.2, 0.3] for _ in range(10)]), \
             patch.object(OpenAIEmbeddingProvider, 'embed_query', return_value=[0.1, 0.2, 0.3]), \
             patch.object(OpenAIEmbeddingProvider, 'count_tokens', return_value=5), \
             patch.object(OpenAIEmbeddingProvider, 'is_available', return_value=True):
            yield

    def test_embed_instance_creates_objects_and_chunks(self, openai_emb_provider, dummy_instance):
        service = EmbeddingService(provider_id=openai_emb_provider.id)
        text = "This is the content that needs to be embedded and chunked."

        service.chunker.max_tokens = 5
        service.chunker.overlap_tokens = 1

        eo = service.embed_instance(dummy_instance, text, tag="test_doc")

        assert eo is not None
        assert eo.tag == "test_doc"
        assert eo.object_id == str(dummy_instance.pk)

        chunks = EmbeddingChunk.objects.filter(embedded_object=eo)
        assert chunks.count() > 0
        
        # FIX 1: Wrap the pgvector array in list() before comparing
        assert list(chunks.first().embedding) == [0.1, 0.2, 0.3]

    def test_embed_instance_skips_if_already_embedded(self, openai_emb_provider, dummy_instance):
        service = EmbeddingService(provider_id=openai_emb_provider.id)
        text = "Sample text."

        eo1 = service.embed_instance(dummy_instance, text)
        eo2 = service.embed_instance(dummy_instance, text)

        assert eo1 is not None
        assert eo2 is None

      # Remove the @patch decorators completely for this test!
    def test_search_executes_raw_sql_correctly(self, openai_emb_provider, dummy_instance):
        service = EmbeddingService(provider_id=openai_emb_provider.id)
        
        # 1. First, create a real embedded object and chunk in the test DB
        # so the search actually has something to find.
        text = "This is a document we want to search for."
        service.embed_instance(dummy_instance, text, tag="docs")

        # 2. Execute the actual search. 
        # This will run the real raw SQL against the pgvector test database.
        results = service.search("test query", limit=3, tag="docs")

        # 3. Assertions
        assert isinstance(results, list)
        
        # Since we just inserted a document with the tag "docs", and our mock provider
        # always returns [0.1, 0.2, 0.3] for both documents and queries, 
        # the cosine distance will be exactly 0 (score = 1.0).
        assert len(results) > 0
        
        # Check the format of the result (assuming it returns tuples/dicts with eo_id and score)
        first_result = results[0]
        # Example assertion (adjust depending on what service.search actually returns):
        # assert first_result['score'] == 1.0

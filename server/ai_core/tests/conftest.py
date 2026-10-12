import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from ai_core.models import LLMProvider, AITaskConfig
from ai_core.models import EmbeddingProvider

@pytest.fixture
def openai_provider():
    return LLMProvider.objects.create(
        name="OpenAI GPT-4",
        provider_type="openai",
        model_name="gpt-4",
        max_context_tokens=8000
    )

@pytest.fixture
def gemini_provider():
    return LLMProvider.objects.create(
        name="Google Gemini",
        provider_type="gemini",
        model_name="gemini-pro"
    )

@pytest.fixture
def chat_config(openai_provider):
    # Patching auto-populate to keep test state isolated and predictable
    with patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True):
        return AITaskConfig.objects.create(
            task_type="chat",
            provider=openai_provider,
            is_default_for_chat=True
        )

@pytest.fixture
def fact_config(gemini_provider):
    with patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True):
        return AITaskConfig.objects.create(
            task_type="fact_extraction",
            provider=gemini_provider
        )


@pytest.fixture(autouse=True)
def mock_tasks():
    """Prevent Celery tasks from firing during tests."""
    with patch("ai_core.models.EmbeddingProvider.start_reembedding_cycle"), \
         patch("ai_core.tasks.download_embedding_model.delay"):
        yield

@pytest.fixture
def openai_emb_provider():
    return EmbeddingProvider.objects.create(
        name="OpenAI Embeddings",
        provider_type="openai",
        api_key="test-key",
        model_name="text-embedding-3-small",
        dimension=1536,
        max_tokens=8192,
        is_active=True,
        is_serving=True
    )

@pytest.fixture
def hf_local_provider():
    return EmbeddingProvider.objects.create(
        name="Local HF",
        provider_type="hf_local",
        model_name="all-MiniLM-L6-v2",
        dimension=384,
        max_tokens=512,
        is_active=False,
        is_serving=False
    )

@pytest.fixture
def dummy_instance():
    User = get_user_model()
    return User.objects.create(email="test@example.com", password='testpassword')


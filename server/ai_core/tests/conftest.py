import pytest
from unittest.mock import patch
from ai_core.models import LLMProvider, AITaskConfig

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
def summary_config(gemini_provider):
    with patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True):
        return AITaskConfig.objects.create(
            task_type="summarization",
            provider=gemini_provider
        )

import pytest
from ai_core.models import LLMProvider
from ai_core.services.llm_service import LLMService


@pytest.fixture
def test_provider(db):
    provider, _ = LLMProvider.objects.update_or_create(
        provider_type="ollama",
        defaults={
            "name": "Ollama Test",
            "base_url": "http://localhost:11434",
            "model_name": "gemma3:1b",
            "is_active": True,
        },
    )

    return provider


@pytest.mark.django_db
class TestLLMStreaming:

    def test_stream(self, test_provider):
        prompt = "Repeat the word 'apple'. don't say anything else"

        print("\n--- LLM STREAM START ---\n")

        llm_service = LLMService()

        full_response = ""

        for chunk in llm_service.stream(prompt):
            print(chunk, end="", flush=True)
            full_response += chunk

        print("\n\n--- LLM STREAM END ---")

        assert len(full_response) > 0

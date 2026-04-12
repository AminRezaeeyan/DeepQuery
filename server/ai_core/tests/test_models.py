import pytest
from django.core.exceptions import ValidationError
from unittest.mock import patch

from ai_core.models import LLMProvider, AITaskConfig

@pytest.mark.django_db
class TestLLMProvider:

    def test_str_returns_name_and_type(self, openai_provider):
        assert str(openai_provider) == "OpenAI GPT-4 (openai)"

    def test_context_limit_property_returns_max_tokens(self, openai_provider):
        assert openai_provider.context_limit == 8000

    def test_delete_without_tasks_succeeds(self, gemini_provider):
        gemini_provider.delete()
        assert LLMProvider.objects.filter(id=gemini_provider.id).exists() is False

    def test_delete_with_tasks_raises_validation_error(self, chat_config, openai_provider):
        with pytest.raises(ValidationError) as exc_info:
            openai_provider.delete()
            
        assert "assigned to one or more tasks" in str(exc_info.value)
        assert LLMProvider.objects.filter(id=openai_provider.id).exists() is True


@pytest.mark.django_db
class TestAITaskConfig:

    @patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True)
    @patch("ai_core.models.AITaskConfig._auto_populate_if_first", create=True)
    def test_clean_allows_multiple_chat_providers(self, mock1, mock2, chat_config, gemini_provider):
        # We already have an openai_provider assigned to "chat"
        # Adding a second one for "chat" should succeed
        new_chat_config = AITaskConfig(
            task_type="chat",
            provider=gemini_provider,
            is_default_for_chat=False
        )
        new_chat_config.full_clean() # Should not raise
        new_chat_config.save()
        
        assert AITaskConfig.objects.filter(task_type="chat").count() == 2

    @patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True)
    @patch("ai_core.models.AITaskConfig._auto_populate_if_first", create=True)
    def test_clean_prevents_multiple_non_chat_providers(self, mock1, mock2, summary_config, openai_provider):
        # We already have a gemini_provider assigned to "summarization"
        invalid_config = AITaskConfig(
            task_type="summarization",
            provider=openai_provider
        )
        
        with pytest.raises(ValidationError) as exc_info:
            invalid_config.full_clean()
            
        assert "may only have one assigned provider" in str(exc_info.value)

    @patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True)
    @patch("ai_core.models.AITaskConfig._auto_populate_if_first", create=True)
    def test_save_ensures_single_default_chat_provider(self, mock1, mock2, chat_config, gemini_provider):
        assert chat_config.is_default_for_chat is True

        # Save a new default chat provider
        new_default = AITaskConfig.objects.create(
            task_type="chat",
            provider=gemini_provider,
            is_default_for_chat=True
        )

        chat_config.refresh_from_db()
        
        assert new_default.is_default_for_chat is True
        # The old one should automatically be set to False
        assert chat_config.is_default_for_chat is False

    def test_auto_populate_creates_all_tasks_if_first_provider(self, openai_provider):
        # Create without mocking the auto-populate methods
        config = AITaskConfig(
            task_type="chat",
            provider=openai_provider,
            is_default_for_chat=True
        )
        
        # Trigger the method explicitly to test its logic
        config._auto_populate_if_first_provider()
        
        # Check that it generated configs for the choices
        assert AITaskConfig.objects.filter(task_type="chat").exists()
        assert AITaskConfig.objects.filter(task_type="summarization").exists()
        assert AITaskConfig.objects.filter(task_type="embedding").exists()

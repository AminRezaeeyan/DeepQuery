import pytest
from unittest.mock import patch

from ai_core.models import AITaskConfig
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.task_provider_resolver import TaskProviderResolver
from ai_core.llm_providers.factory import ProviderFactory


class MockProviderInstance:
    def __init__(self, provider_model):
        self.provider_model = provider_model


@pytest.mark.django_db
class TestTaskProviderResolver:

    def test_get_provider_defaults_to_default_chat(self, chat_config, summary_config):
        provider = TaskProviderResolver.get_provider_for_task()
        assert provider == chat_config.provider

    def test_get_provider_with_id_and_non_chat_fails(self):
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(task_type="summarization", provider_id=1)
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

    def test_get_specific_chat_provider_not_assigned_to_chat(self, summary_config):
        # We pass a valid provider ID, but it is only configured for summarization, not chat
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(
                task_type="chat", 
                provider_id=summary_config.provider.id
            )
        assert "not assigned to chat" in str(exc.value)

    def test_get_provider_by_task_type_success(self, summary_config):
        provider = TaskProviderResolver.get_provider_for_task(task_type="summarization")
        assert provider == summary_config.provider

    def test_get_provider_fails_when_none_configured(self):
        with pytest.raises(ProviderUnavailable) as exc:
            TaskProviderResolver.get_provider_for_task(task_type="fact_extraction")
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

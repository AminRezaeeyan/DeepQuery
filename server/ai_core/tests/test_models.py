import pytest
from django.core.exceptions import ValidationError
from unittest.mock import patch

from ai_core.models import LLMProvider, AITaskConfig, EmbeddingProvider

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
    def test_clean_prevents_multiple_non_chat_providers(self, mock1, mock2, fact_config, openai_provider):
        # We already have a gemini_provider assigned to "fact_extraction"
        invalid_config = AITaskConfig(
            task_type="fact_extraction",
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
        assert AITaskConfig.objects.filter(task_type="web_query_generation").exists()
        assert AITaskConfig.objects.filter(task_type="fact_extraction").exists()


@pytest.mark.django_db
class TestEmbeddingProviderValidation:

    def test_missing_model_name_raises_validation_error(self):
        provider = EmbeddingProvider(
            name="Test",
            provider_type="openai",
            api_key="key",
            dimension=1536
        )
        with pytest.raises(ValidationError) as exc:
            provider.clean()
        assert "model_name is required" in str(exc.value)

    def test_missing_api_key_for_remote_provider_raises_error(self):
        provider = EmbeddingProvider(
            name="Test",
            provider_type="openai",
            model_name="test-model",
            dimension=1536
        )
        with pytest.raises(ValidationError) as exc:
            provider.clean()
        assert "API key is required" in str(exc.value)

    def test_downloading_status_on_remote_provider_raises_error(self):
        provider = EmbeddingProvider(
            name="Test",
            provider_type="openai",
            api_key="key",
            model_name="test-model",
            dimension=1536,
            status="downloading"
        )
        with pytest.raises(ValidationError) as exc:
            provider.clean()
        assert "Only local providers can have 'downloading' status" in str(exc.value)

@pytest.mark.django_db
class TestEmbeddingProviderSaveLogic:

    def test_first_provider_becomes_active_and_serving(self):
        # Database is initially empty
        provider = EmbeddingProvider(
            name="First",
            provider_type="hf_local",
            model_name="test-model",
            dimension=384
        )
        provider.save()
        
        assert provider.is_active is True
        assert provider.is_serving is True

    def test_saving_new_active_provider_deactivates_old_ones(self, openai_emb_provider):
        assert openai_emb_provider.is_active is True

        new_provider = EmbeddingProvider.objects.create(
            name="New Active",
            provider_type="hf_local",
            model_name="test",
            dimension=128,
            is_active=True 
        )

        openai_emb_provider.refresh_from_db()
        assert openai_emb_provider.is_active is False
        assert new_provider.is_active is True

    @patch("ai_core.tasks.download_embedding_model.delay")
    def test_saving_new_hf_local_triggers_download(self, mock_delay):
        provider = EmbeddingProvider.objects.create(
            name="New HF",
            provider_type="hf_local",
            model_name="test",
            dimension=128
        )
        mock_delay.assert_called_once_with(provider.id)


@pytest.mark.django_db
class TestEmbeddingProviderDeleteLogic:

    def test_cannot_delete_active_provider(self, openai_emb_provider):
        openai_emb_provider.is_serving = False
        with pytest.raises(ValidationError) as exc:
            openai_emb_provider.delete()
        assert "Cannot delete the active embedding provider" in str(exc.value)

    def test_cannot_delete_serving_provider(self, openai_emb_provider):
        # Make it inactive but serving
        openai_emb_provider.is_active = False
        openai_emb_provider.save(update_fields=["is_active"])

        with pytest.raises(ValidationError) as exc:
            openai_emb_provider.delete()
        assert "Cannot delete provider currently serving" in str(exc.value)

    def test_cannot_delete_reembedding_provider(self, hf_local_provider):
        hf_local_provider.status = "reembedding"
        hf_local_provider.save()

        with pytest.raises(ValidationError) as exc:
            hf_local_provider.delete()
        assert "Cannot delete a provider while re-embedding is running" in str(exc.value)

    def test_successful_deletion(self, hf_local_provider):
        # hf_local_provider is not active, serving, or reembedding
        hf_local_provider.status = "ready"
        hf_local_provider.is_serving = False
        hf_local_provider.is_active = False
        provider_id = hf_local_provider.id

        hf_local_provider.delete()
        assert EmbeddingProvider.objects.filter(id=provider_id).exists() is False


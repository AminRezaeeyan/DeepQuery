from ai_core.models import AITaskConfig
from ai_core.exceptions import ProviderUnavailable


class ProviderService:

    @staticmethod
    def get_default_chat_provider():
        task_config = (
            AITaskConfig.objects
            .select_related("provider")
            .filter(task_type="chat", is_default_for_chat=True)
            .first()
        )

        if not task_config:
            raise ProviderUnavailable("No default chat LLM provider configured")

        return task_config.provider


    @staticmethod
    def get_default_chat_provider_id():
        task_config = (
            AITaskConfig.objects
            .filter(task_type="chat", is_default_for_chat=True)
            .only("provider_id")
            .first()
        )

        if not task_config:
            raise ProviderUnavailable("No default chat LLM provider configured")

        return task_config.provider_id


    @staticmethod
    def get_chat_provider(provider_id):
        task_config = (
            AITaskConfig.objects
            .select_related("provider")
            .filter(
                provider_id=provider_id,
                task_type="chat"
            )
            .first()
        )

        if not task_config:
            raise ProviderUnavailable("Provider is not available for chat")

        return task_config.provider


    @staticmethod
    def validate_chat_provider_id(provider_id):
        exists = AITaskConfig.objects.filter(
            provider_id=provider_id,
            task_type="chat"
        ).exists()

        if not exists:
            raise ProviderUnavailable("Provider is not available for chat")

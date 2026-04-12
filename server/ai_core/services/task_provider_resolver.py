from ai_core.models import AITaskConfig, LLMProvider
from ai_core.exceptions import ProviderUnavailable


class TaskProviderResolver:

    @staticmethod
    def get_provider_for_task(task_type: str | None = None,
                              provider_id: int | None = None) -> LLMProvider:

        if task_type is None:
            task_type = "chat"

        if task_type != "chat" and provider_id is not None:
            raise ProviderUnavailable(
                "provider_id is only allowed when requesting a chat provider."
            )

        if provider_id is not None and task_type == "chat":
            provider = LLMProvider.objects.filter(id=provider_id).first()
            if not provider:
                raise ProviderUnavailable("Requested provider not found.")

            if not AITaskConfig.objects.filter(
                task_type="chat", provider=provider
            ).exists():
                raise ProviderUnavailable(
                    "The selected provider is not assigned to chat."
                )

            return provider

        config = (
            AITaskConfig.objects
            .select_related("provider")
            .filter(task_type=task_type)
            .first()
        )

        if config:
            return config.provider

        if task_type == "chat":
            default_chat = (
                AITaskConfig.objects
                .select_related("provider")
                .filter(task_type="chat", is_default_for_chat=True)
                .first()
            )
            if default_chat:
                return default_chat.provider

        raise ProviderUnavailable(
            f"No provider configured for task '{task_type}'."
        )

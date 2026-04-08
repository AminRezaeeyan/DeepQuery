from ai_core.services.llm_service import LLMService
from ai_core.services.token_service import TokenService
from ai_core.exceptions import ContextLimitExceededError

class ChatGenerationService:
    """
    ChatGenerationService orchestrates high-level AI logic:
    - system prompts
    - conversation shaping
    - RAG injection
    - memory injection
    - safety & policy layers
    - calling LLMService as the final step
    """

    def __init__(self, provider_id=None):
        self.llm = LLMService(provider_id)
        self.provider_config = self.llm.provider_config
        self.prompt_builder = PromptBuilder(self.provider_config.max_context_tokens)

    def stream_answer(self, user_prompt: str):

        system_prompt = (
            "You are a helpful AI assistant. "
            "Keep responses concise, accurate, and helpful."
        )

        self.prompt_builder.allocate(system_prompt, user_prompt)

        messages = self.prompt_builder.build_messages(
            system_prompt,
            user_prompt
        )

        for token in self.llm.stream(messages):
            yield token


class PromptBuilder:
    """
    Responsible for:
    - calculating prompt budgets
    - allocating memory / knowledge budgets
    - building the final prompt messages
    """

    BASE_LIMIT_RATIO = 0.8
    LONG_TERM_MEMORY_TOKENS = 500

    def __init__(self, max_context_tokens: int):
        self.max_context_tokens = max_context_tokens

    def allocate(self, system_prompt: str, user_prompt: str) -> dict:

        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        base_tokens = TokenService.count_message_list(base_messages)

        available_budget = TokenService.get_available_budget(
            self.max_context_tokens
        )

        base_limit = int(available_budget * self.BASE_LIMIT_RATIO)

        if base_tokens > base_limit:
            raise ContextLimitExceededError(
                "Prompt is too large for the model context window."
            )

        remaining = max(0, available_budget - base_tokens)

        long_term_budget = min(self.LONG_TERM_MEMORY_TOKENS, remaining)

        remaining -= long_term_budget

        knowledge_budget = remaining // 2
        short_term_budget = remaining - knowledge_budget

        return {
            "base_tokens": base_tokens,
            "long_term_memory": long_term_budget,
            "knowledge_base": knowledge_budget,
            "short_term_memory": short_term_budget,
        }

    def build_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        """
        Current structure:

        system
        long_term_memory (future)
        knowledge_base (future)
        short_term_memory (future)
        user
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return messages

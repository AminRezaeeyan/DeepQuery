from ai_core.services.llm_service import LLMService
from ai_core.services.token_service import TokenService
from ai_core.exceptions import ContextLimitExceededError
from ai_core.services.memory.short_term_memory import ShortTermMemory
from ai_core.services.memory.long_term_memory import LongTermMemoryService
from ai_core.services.document_rag_service import DocumentRAGService

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

    def __init__(self, user_id, chat_id, provider_id=None, is_temporary=False):
        self.user_id = user_id
        self.chat_id = chat_id
        self.is_temporary = is_temporary
        self.llm = LLMService(provider_id=provider_id, task_type='chat')
        self.provider_config = self.llm.provider_config
        self.prompt_builder = PromptBuilder(self.provider_config.max_context_tokens)
        self.memory = LongTermMemoryService(user_id=user_id, enabled= not is_temporary)
        self.document_rag = DocumentRAGService(chat_id=chat_id)

    def stream_answer(self, user_prompt: str):
        system_prompt = (
            "You are a helpful AI assistant. "
            "Provide accurate, clear, and concise answers."
        )

        budgets = self.prompt_builder.allocate(system_prompt, user_prompt)

        # Long-term memory (skip if temporary)
        memory_block = ""
        if not self.is_temporary:
            memory_block = self.memory.build_memory_context(
                query=user_prompt,
                token_limit=budgets["long_term_memory"],
                max_candidates=20,
            )

        # Document RAG
        knowledge_block = self.document_rag.build_knowledge_context(
            query=user_prompt,
            token_limit=budgets["knowledge_base"],
            max_candidates=10,
        )
        # Short-term memory (chat history)
        short_term_memory = ShortTermMemory(
            chat_id=self.chat_id,
            token_limit=budgets["short_term_memory"],
        )
        short_term_messages = short_term_memory.collect()

        # Build prompt
        messages = self.prompt_builder.build_messages(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            short_term_memory=short_term_messages,
            long_term_memory=memory_block,
            knowledge_block=knowledge_block,  # ✨ document injection here
        )

        # Background memory write
        if not self.is_temporary:
            self.memory.store_from_message(self.chat_id, user_prompt)

        # Stream LLM output
        for token in self.llm.stream(messages):
            yield token



class PromptBuilder:

    BASE_LIMIT_RATIO = 0.8
    LONG_TERM_MEMORY_TOKENS = 500

    def __init__(self, max_context_tokens: int):
        self.max_context_tokens = max_context_tokens

    def allocate(self, system_prompt: str, user_prompt: str):

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

    def build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        short_term_memory: list | None = None,
        long_term_memory: str | None = None,
        knowledge_block: str | None = None,
    ):
            messages = [{"role": "system", "content": system_prompt}]

            if long_term_memory:
                messages.append({
                    "role": "system",
                    "content": (
                        "The following facts are long-term memories about the user. "
                        "Use them when relevant.\n\n"
                        f"{long_term_memory}"
                    ),
                })

            if knowledge_block:
                messages.append({
                    "role": "system",
                    "content": (
                        "The following information is extracted from the user's uploaded documents "
                        "for this chat. Treat it as authoritative reference when relevant.\n\n"
                        f"{knowledge_block}"
                    ),
                })

            if short_term_memory:
                messages.extend(short_term_memory)

            messages.append({"role": "user", "content": user_prompt})
            return messages

    

class ChatTitleGenerator:
    SYSTEM_PROMPT = (
        "You generate extremely short, human-friendly conversation titles. "
        "Rules:\n"
        "- Maximum 6 words\n"
        "- No quotes\n"
        "- No ending punctuation\n"
        "- Title must summarize the user's first message\n"
        "- Be concise and specific"
    )

    def __init__(self):
        self.llm = LLMService(task_type="title_generation")

    def generate(self, first_user_message: str) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": first_user_message},
        ]

        stream = self.llm.stream(messages=messages)

        title = ""

        for token in stream:
            title += str(token)

        title = title.strip().replace('"', '').replace("'", "")[:80]

        return title
import tiktoken


class TokenService:
    """
    Token estimation service.

    Uses a universal tokenizer (cl100k_base) which works reasonably well
    across most modern LLMs (OpenAI, Claude, Gemini approximations).
    """

    _enc = tiktoken.get_encoding("cl100k_base")

    SAFETY_RATIO = 0.1

    @classmethod
    def count_tokens(cls, text: str) -> int:
        if not text:
            return 0
        return len(cls._enc.encode(text))

    @classmethod
    def count_message_list(cls, messages: list[dict]) -> int:
        """
        Estimate tokens for a list of messages:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."}
        ]
        """

        total = 0

        for msg in messages:
            total += cls.count_tokens(msg.get("content", ""))

            # structural overhead per message
            total += 4

        return total
    
    @classmethod
    def get_output_reserve(cls, max_context_tokens: int) -> int:
        """
        Return reserved output tokens based on realistic API caps.
        """
        
        if max_context_tokens <= 8_192:
            return 2048

        if max_context_tokens <= 32_768:
            return 4096

        # Most 128k models hard-cap output at 4k tokens.
        if max_context_tokens <= 131_072:
            return 4096 

        # The highest standard output cap across major providers is currently 8k.
        return 8192


    @classmethod
    def get_available_budget(
        cls,
        max_context_tokens: int,
        output_limit: int | None = None,
    ) -> int:
        """
        Calculate safe prompt token budget.

        Formula:
        available = max_context - output_limit - safety_margin
        """

        if output_limit is None:
            output_limit = cls.get_output_reserve(max_context_tokens)

        safety_margin = int(max_context_tokens * cls.SAFETY_RATIO)

        available = max_context_tokens - output_limit - safety_margin

        return max(0, available)

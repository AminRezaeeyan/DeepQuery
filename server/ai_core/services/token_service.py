import tiktoken

class TokenService:
    """
    Token estimation service.
    Uses one universal tokenizer (e.g., cl100k_base) for all LLMs.
    """

    _enc = tiktoken.get_encoding("cl100k_base")

    @classmethod
    def count_tokens(cls, text: str) -> int:
        if not text:
            return 0
        return len(cls._enc.encode(text))

    @classmethod
    def count_message_list(cls, messages: list[dict]) -> int:
        """
        Count tokens for a list of messages like:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            ...
        ]
        """
        total = 0
        for msg in messages:
            total += cls.count_tokens(msg.get("content", ""))
        return total

        #TODO: LLMs add other stuff to messages like role and so on. we should add them later.

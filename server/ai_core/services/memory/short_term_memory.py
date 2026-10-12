from ai_core.services.token_service import TokenService


class ShortTermMemory:

    PAGE_SIZE = 20

    def __init__(self, chat_id, token_limit, before=None):
        self.chat_id = chat_id
        self.token_limit = token_limit
        # Only messages older than this; the current question is sent separately.
        self.before = before

    def collect(self):
        from chats.services.chat_service import ChatService
        cursor = self.before
        total_tokens = 0
        messages = []

        while True:

            batch, cursor = ChatService.get_message_pairs(
                chat_id=self.chat_id,
                cursor=cursor,
                limit=self.PAGE_SIZE
            )

            if not batch:
                break

            for msg in batch:
                tokens = TokenService.count_tokens(msg["content"])

                if total_tokens + tokens > self.token_limit:
                    return list(reversed(messages))

                messages.append(msg)
                total_tokens += tokens

        return list(reversed(messages))

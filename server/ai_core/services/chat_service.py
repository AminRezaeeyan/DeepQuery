from ai_core.services.llm_service import LLMService

class ChatService:
    """
    ChatService orchestrates high-level AI logic:
    - system prompts
    - conversation shaping
    - RAG injection
    - memory injection
    - safety & policy layers
    - calling LLMService as the final step
    """

    def __init__(self):
        self.llm = LLMService()

    def stream_answer(self, user_prompt: str):
       

        system_prompt = (
            "You are a helpful AI assistant. "
            "Keep responses concise, accurate, and helpful."
        )

        final_prompt = f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:"

        # Stream from LLMService
        for token in self.llm.stream(final_prompt):
            yield token

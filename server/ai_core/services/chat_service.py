from ai_core.services.llm_service import LLMService
from ai_core.services.token_service import TokenService
from ai_core.exceptions import ContextLimitExceededError
from ai_core.services.memory.short_term_memory import ShortTermMemory
from ai_core.services.memory.long_term_memory import LongTermMemoryService
from ai_core.services.document_rag_service import DocumentRAGService
from ai_core.services.web_search_service import WebKnowledgeService

class ChatGenerationService:
    def __init__(self, user_id, chat_id, provider_id=None, is_temporary=False, enable_web_search=False, strict_quote_mode=False, audience_type="General", reasoning_depth="Medium", challenge_mode=False):
        self.user_id = user_id
        self.chat_id = chat_id
        self.is_temporary = is_temporary
        self.enable_web_search = enable_web_search
        self.llm = LLMService(provider_id=provider_id, task_type='chat')
        self.provider_config = self.llm.provider_config
        self.prompt_builder = PromptBuilder(self.provider_config.max_context_tokens)
        self.memory = LongTermMemoryService(user_id=user_id, enabled= not is_temporary)
        self.document_rag = DocumentRAGService(chat_id=chat_id)
        self.web_service = WebKnowledgeService(chat_id, user_id)
        self.strict_quote_mode = strict_quote_mode
        self.audience_type = audience_type
        self.reasoning_depth = reasoning_depth
        self.challenge_mode = challenge_mode

    def _get_system_prompt(self):
        depth_instruction = {
            "Low": "Provide a concise summary in 2-3 sentences.",
            "Medium": "Provide a clear, balanced explanation.",
            "High": "Provide an exhaustive, multi-section analysis with deep logical derivation."
        }
        
        prompt = (
            f"You are an expert Research Assistant. Tailor your tone to an {self.audience_type} audience.\n"
            "RULES:\n"
            "1. EVIDENCE-BASED: Rely EXCLUSIVELY on the provided context. If an answer isn't in the context, state it.\n"
            "2. CITATION: You MUST cite claims using [Source ID] (e.g., [1]). If multiple support a claim, use [1][2].\n"
            "3. CONFLICTS: If sources contradict, highlight it: 'Source [1] says X, but Source [2] says Y.'\n"
            f"4. DEPTH: {depth_instruction.get(self.reasoning_depth, depth_instruction['Medium'])}\n"
        )
        
        if self.strict_quote_mode:
            prompt += "5. STRICT QUOTE: Include direct verbatim quotes for every major claim.\n"
        
        if self.challenge_mode:
            prompt += "6. CHALLENGE: Critically analyze your synthesis for gaps, biases, or missing perspectives.\n"
            
        return prompt

        
    def stream_answer(self, user_prompt: str, image_bytes: bytes = None, mime_type: str = None, history_before=None):
        system_prompt = self._get_system_prompt()
        budgets = self.prompt_builder.allocate(system_prompt, user_prompt)

         # 1. Fetch, clean, and embed web data directly into the unified vector DB
        if self.enable_web_search:
            self.web_service.gather_and_embed(prompt=user_prompt)

        # 2. Long-term memory (skip if temporary)
        memory_block = ""
        if not self.is_temporary:
            memory_block = self.memory.build_memory_context(
                query=user_prompt,
                token_limit=budgets["long_term_memory"],
                max_candidates=20,
            )

        # 3. Unified Document RAG (Retrieves both File and Web chunks)
        # Using the entire knowledge_base budget since web and files are merged
        _, rag_results = self.document_rag.build_knowledge_context(
            query=user_prompt,
            token_limit=budgets["knowledge_base"],
            max_candidates=15,
        )

        # 4. Format Context & Generate Citation Map
        formatted_knowledge_block = ""
        citation_map = {}
        
        if rag_results:
            doc_counter = 1
            # Unpacking Document instance and score based on DocumentRAGService
            for obj, score, text in rag_results:
                doc_id = obj.id
                if doc_id not in citation_map:
                    citation_map[doc_id] = {
                        "cite_id": doc_counter,
                        "url": getattr(obj, "source_url", None),
                        "filename": getattr(obj, "original_filename", "File")
                    }
                    doc_counter += 1
                    
                cite_id = citation_map[doc_id]["cite_id"]

                if text:
                    formatted_knowledge_block += f"--- Source [{cite_id}] ---\n{text}\n\n"

        # 5. Short-term memory (chat history)
        short_term_memory = ShortTermMemory(
            chat_id=self.chat_id,
            token_limit=budgets["short_term_memory"],
            before=history_before,
        )
        short_term_messages = short_term_memory.collect()

        # 6. Build final prompt
        messages = self.prompt_builder.build_messages(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            short_term_memory=short_term_messages,
            long_term_memory=memory_block,
            knowledge_block=formatted_knowledge_block,
        )

        # Background memory write
        if not self.is_temporary:
            self.memory.store_from_message(self.chat_id, user_prompt)
        print(messages)
        # Stream LLM output
        for token in self.llm.stream(messages, image_bytes=image_bytes, mime_type=mime_type):
            yield token

        # 8. Append References List at the end of the stream
        if citation_map:
            yield "\n\n**References:**\n"
            sorted_cites = sorted(citation_map.values(), key=lambda x: x["cite_id"])
            for cit in sorted_cites:
                source_name = cit["url"] if cit["url"] else cit["filename"]
                yield f"[{cit['cite_id']}] {source_name}\n"
#

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
        available_budget = TokenService.get_available_budget(self.max_context_tokens)
        base_limit = int(available_budget * self.BASE_LIMIT_RATIO)

        if base_tokens > base_limit:
            raise ContextLimitExceededError(
                "Prompt is too large for the model context window."
            )

        remaining = max(0, available_budget - base_tokens)

        long_term_budget = min(self.LONG_TERM_MEMORY_TOKENS, remaining)
        remaining -= long_term_budget

        # Unified Knowledge budget (no longer split)
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
                    "and requested web searches. Treat it as authoritative reference. "
                    "Always cite the Source ID when using this information.\n\n"
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
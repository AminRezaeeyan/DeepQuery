import re
from ai_core.services.llm_service import LLMService

class FactExtractor:

    # Rich patterns covering personal facts
    FACT_PATTERNS = [
        # Identity
        r"\bI am ([A-Za-z ]+)\b",
        r"\bmy name is ([A-Za-z ]+)\b",
        r"\bI'?m called ([A-Za-z ]+)\b",
        r"\bcall me ([A-Za-z ]+)\b",
        
        # Age
        r"\bI am (\d+) years? old\b",
        r"\bI'?m (\d+)\b",
        r"\bI turned (\d+)\b",
        
        # Location
        r"\bI live in ([A-Za-z ]+)\b",
        r"\bI'?m from ([A-Za-z ]+)\b",
        r"\bI'?m based in ([A-Za-z ]+)\b",
        r"\bI moved to ([A-Za-z ]+)\b",
        r"\bI grew up in ([A-Za-z ]+)\b",
        
        # Work/Education
        r"\bI work (as|at) ([A-Za-z ]+)\b",
        r"\bI'?m a ([A-Za-z ]+)\b",
        r"\bmy job is ([A-Za-z ]+)\b",
        r"\bI study ([A-Za-z ]+)\b",
        r"\bI'?m studying ([A-Za-z ]+)\b",
        r"\bI major in ([A-Za-z ]+)\b",
        r"\bI graduated from ([A-Za-z ]+)\b",
        
        # Preferences
        r"\bI like ([A-Za-z ]+)\b",
        r"\bI love ([A-Za-z ]+)\b",
        r"\bI prefer ([A-Za-z ]+)\b",
        r"\bI enjoy ([A-Za-z ]+)\b",
        r"\bI hate ([A-Za-z ]+)\b",
        r"\bI dislike ([A-Za-z ]+)\b",
        r"\bI can'?t stand ([A-Za-z ]+)\b",
        r"\bmy favorite ([A-Za-z ]+) is\b",
        r"\bI'?m a fan of ([A-Za-z ]+)\b",
        
        # Hobbies/Skills
        r"\bI play ([A-Za-z ]+)\b",
        r"\bI practice ([A-Za-z ]+)\b",
        r"\bI do ([A-Za-z ]+)\b",
        r"\bI'?m learning ([A-Za-z ]+)\b",
        r"\bI know how to ([A-Za-z ]+)\b",
        r"\bI can ([A-Za-z ]+)\b",
        r"\bI speak ([A-Za-z ]+)\b",
        
        # Relationships
        r"\bI have a ([A-Za-z ]+)\b",
        r"\bmy ([A-Za-z]+) is ([A-Za-z ]+)\b",
        r"\bI'?m married to ([A-Za-z ]+)\b",
        r"\bI have (\d+) (kids|children|siblings)\b",
        
        # Habits/Routine
        r"\bI usually ([A-Za-z ]+)\b",
        r"\bI always ([A-Za-z ]+)\b",
        r"\bI never ([A-Za-z ]+)\b",
        r"\bI often ([A-Za-z ]+)\b",
        r"\bevery day I ([A-Za-z ]+)\b",
        
        # Goals/Plans
        r"\bI want to ([A-Za-z ]+)\b",
        r"\bI plan to ([A-Za-z ]+)\b",
        r"\bI'?m planning to ([A-Za-z ]+)\b",
        r"\bmy goal is to ([A-Za-z ]+)\b",
        
        # Physical/Health
        r"\bI'?m allergic to ([A-Za-z ]+)\b",
        r"\bI have ([A-Za-z ]+) allergy\b",
        r"\bI'?m vegetarian\b",
        r"\bI'?m vegan\b",
        r"\bI don'?t eat ([A-Za-z ]+)\b",
    ]

    # Persian triggers. "\u200c" is the zero-width non-joiner that often sits
    # inside verbs (می‌کنم), so each verb accepts it, a space, or nothing.
    PERSIAN_FACT_PATTERNS = [
        # Identity, age, origin
        r"(اسمم|اسم من|نامم|نام من)",
        r"[\d۰-۹]+\s*سال(مه|م|ه|ه‌ام)",
        r"(ساکن|اهل|متولد)\s",
        r"من\s.+\s?هستم",
        # Work and study
        r"(زندگی|کار|تحصیل)\s*می[\u200c ]?کنم",
        r"(شغلم|شغل من|رشته[\u200c ]?ام|رشته من)",
        r"(دانشجوی|فارغ[\u200c ]?التحصیل)",
        # Preferences
        r"(دوست دارم|دوست ندارم|عاشق|متنفرم|علاقه دارم|علاقه[\u200c ]?مندم|ترجیح می[\u200c ]?دهم)",
        # Family
        r"(همسرم|پسرم|دخترم|برادرم|خواهرم|پدرم|مادرم|فرزند|بچه[\u200c ]?هایم)",
        # Skills, goals, health
        r"(بلدم|یاد می[\u200c ]?گیرم|صحبت می[\u200c ]?کنم)",
        r"(قصد دارم|هدفم|برنامه دارم)",
        r"(حساسیت دارم|گیاه[\u200c ]?خوار|وگان)",
    ]

    SYSTEM_PROMPT = """
You extract **long-term personal facts** from user messages for memory storage.

**What to extract:**
- Personal identity: name, age, occupation, education, location
- Preferences: favorite things, likes/dislikes, habits
- Relationships: family members, pets, friends
- Skills and hobbies: what they do, learn, or practice
- Important life details: goals, values, background

**What NOT to extract:**
- Temporary states: "I'm tired", "I'm hungry right now"
- Current requests: "I want to know about X"
- Opinions about general topics (unless it's a strong personal preference)
- Conversational filler or questions

**Format rules:**
- Rewrite in third person starting with "User"
- Examples:
  - "I like melon" → "User likes melon"
  - "My name is Alex" → "User's name is Alex"
  - "I work as a teacher" → "User works as a teacher"
- Be concise and factual
- Use present tense for current facts
- Extract ALL distinct facts from the message

**Output format:**
Return a list of facts, one per line. Separate each fact with a newline character.

Example output:
User's name is Alex
User works as a teacher
User likes melon

If no extractable facts exist, return:
null
"""

    def __init__(self, provider_id=None):
        self.provider_id = provider_id

    def extract_facts(self, text: str):
        """Main method"""
        if not self._contains_fact(text):
            return None
        
        facts = self._extract_with_llm(text)
        return facts

        


    def _contains_fact(self, text: str) -> bool:
        """Simple regex-based pre-check to avoid unnecessary LLM calls."""
        for pattern in self.FACT_PATTERNS + self.PERSIAN_FACT_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    def _extract_with_llm(self, text: str):
        """
        Calls LLM to extract and format the fact
        """
        llm = LLMService(provider_id=self.provider_id, task_type="fact_extraction")

        stream = llm.stream([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ])

        raw = ""
        for chunk in stream:
            raw += str(chunk)

        raw = raw.strip()

        if raw.lower() == "null":
            return []
        
        facts = [line.strip() for line in raw.split("\n") if line.strip()]
        return facts
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model

from ai_core.models import MemoryFact
from ai_core.services.memory.fact_extractor import FactExtractor
from ai_core.services.memory.long_term_memory import LongTermMemoryService
from ai_core.tasks import extract_and_embed_facts_task


class TestPersianFactsTriggerExtraction:

    @pytest.mark.parametrize(
        "text",
        [
            "اسم من سارا است",
            "۲۵ سالمه",
            "در تهران زندگی می‌کنم",
            "در تهران زندگی میکنم",
            "من برنامه‌نویس هستم",
            "قهوه را خیلی دوست دارم",
            "به بادام زمینی حساسیت دارم",
        ],
    )
    def test_personal_facts_in_persian_are_detected(self, text):
        assert FactExtractor()._contains_fact(text)

    @pytest.mark.parametrize(
        "text",
        ["خلاصه‌ی این مقاله را بنویس", "Summarize this paper for me"],
    )
    def test_ordinary_questions_skip_the_extractor(self, text):
        assert not FactExtractor()._contains_fact(text)


@pytest.mark.django_db
class TestFactsAreDeduplicatedPerUser:

    def test_a_fact_from_another_chat_is_not_stored_twice(self):
        user = get_user_model().objects.create_user(email="m@example.com", password="password123")
        MemoryFact.objects.create(user=user, chat_id=1, fact="User lives in Tehran")

        with patch("ai_core.tasks.FactExtractor") as extractor, patch("ai_core.tasks.EmbeddingService"):
            extractor.return_value.extract_facts.return_value = ["User lives in Tehran"]
            extract_and_embed_facts_task(user_id=user.id, chat_id=2, text="I live in Tehran")

        assert MemoryFact.objects.filter(user=user).count() == 1


class TestMemoryRelevance:

    def test_weakly_related_memories_stay_out_of_the_prompt(self):
        weak = MemoryFact(user_id=1, fact="User likes jazz")
        strong = MemoryFact(user_id=1, fact="User is allergic to peanuts")

        with patch("ai_core.services.memory.long_term_memory.EmbeddingService") as embedder:
            embedder.return_value.search.return_value = [(weak, 0.2, weak.fact, ""), (strong, 0.8, strong.fact, "")]
            context = LongTermMemoryService(user_id=1).build_memory_context("Is this snack safe for me?", token_limit=500)

        assert "peanuts" in context
        assert "jazz" not in context

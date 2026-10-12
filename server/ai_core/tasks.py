from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from ai_core.services.embedding_service import EmbeddingService
from ai_core.models import EmbeddingProvider, EmbeddedObject, MemoryFact
from ai_core.embedding_providers.factory import EmbeddingProviderFactory
from ai_core.services.memory.fact_extractor import FactExtractor

@shared_task(bind=True)
def download_embedding_model(self, provider_id: int):
    """
    Asynchronously downloads a HuggingFace embedding model.
    Updates provider status:
        downloading → ready
        downloading → error
    """

    provider = EmbeddingProvider.objects.filter(id=provider_id).first()
    if not provider:
        return f"Provider {provider_id} does not exist."
    
    provider.status = "downloading"
    provider.status_message = "Downloading model..."
    provider.save(update_fields=["status", "status_message"])

    try:
        provider_instance = EmbeddingProviderFactory.from_model(provider)
        provider_instance.download_model()

        with transaction.atomic():
            provider.status = "ready"
            provider.status_message = f"Model downloaded successfully at {timezone.now()}"
            provider.save(update_fields=["status", "status_message"])

        return f"Provider {provider_id} download successful."

    except Exception as e:
        with transaction.atomic():
            provider.status = "error"
            provider.status_message = f"Download failed: {str(e)}"
            provider.save(update_fields=["status", "status_message"])

        return f"Provider {provider_id} download failed: {str(e)}"


@shared_task
def reembed_all_objects(new_provider_id):

    service = EmbeddingService(provider_id=new_provider_id)

    unique_objects = (
        EmbeddedObject.objects
        .values("content_type", "object_id", "tag")
        .distinct()
    )

    for entry in unique_objects:
        ct = ContentType.objects.get(id=entry["content_type"])
        model_cls = ct.model_class()
        instance = model_cls.objects.filter(id=entry["object_id"]).first()

        if instance is None:
            continue

        raw_text = text_for_reembedding(instance)

        if not raw_text:
            continue

        service.embed_instance(instance, raw_text, tag=entry["tag"])

    finish_provider_switch(new_provider_id)


# The field holding the text that was embedded, for each embedded model.
EMBEDDED_TEXT_FIELDS = ("extracted_text", "fact")


def text_for_reembedding(instance):
    for field in EMBEDDED_TEXT_FIELDS:
        value = getattr(instance, field, None)
        if value:
            return value
    return None


@transaction.atomic
def finish_provider_switch(new_provider_id):

    new_provider = EmbeddingProvider.objects.get(id=new_provider_id)

    old_provider = EmbeddingProvider.objects.filter(
        is_serving=True
    ).exclude(id=new_provider.id).first()

    # Only one provider may serve at a time, so release the old one first.
    if old_provider:

        EmbeddedObject.objects.filter(
            provider=old_provider
        ).delete()

        old_provider.is_serving = False
        old_provider.save()

    new_provider.is_serving = True
    new_provider.status = "ready"
    new_provider.save()


@shared_task
def extract_and_embed_facts_task(user_id, chat_id, text, provider_id=None):
    """
    Background job:
    1. Load message
    2. Extract facts using FactExtractor
    3. Save MemoryFact rows
    4. Embed each fact using EmbeddingService
    """

    extractor = FactExtractor(provider_id=provider_id)

    facts = extractor.extract_facts(text)

    embed = EmbeddingService(provider_id=provider_id)

    if facts is None:
        return
    
    for fact in facts:

        exists = MemoryFact.objects.filter(
            chat_id=chat_id,
            user_id=user_id,
            fact__iexact=fact.strip()
        ).exists()

        if exists:
            continue

        with transaction.atomic():
            mem = MemoryFact.objects.create(
                chat_id=chat_id,
                user_id=user_id,
                fact=fact.strip(),
            )

        # Step 4 — Embed the fact
        embed.embed_instance(
            instance=mem,
            text=fact,
            tag=f"user:{mem.user_id}"
        )



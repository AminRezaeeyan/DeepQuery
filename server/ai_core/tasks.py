from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import EmbeddingProvider, EmbeddedObject
from .embedding_providers.factory import EmbeddingProviderFactory

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
    
    # Mark as downloading
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

    new_provider = EmbeddingProvider.objects.get(id=new_provider_id)

    provider_instance = EmbeddingProviderFactory.from_model(new_provider)

    objects = EmbeddedObject.objects.all().distinct(
        "content_type",
        "object_id"
    )

    for obj in objects:

        target = obj.target

        if not target:
            continue

        text = str(target)

        embeddings = provider_instance.embed([text])

        new_object = EmbeddedObject.objects.create(
            content_type=obj.content_type,
            object_id=obj.object_id,
            provider=new_provider,
        )

        for i, vector in enumerate(embeddings):

            new_object.chunks.create(
                text=text,
                embedding=vector,
                chunk_index=i
            )

    finish_provider_switch(new_provider_id)


def finish_provider_switch(new_provider_id):

    new_provider = EmbeddingProvider.objects.get(id=new_provider_id)

    old_provider = EmbeddingProvider.objects.filter(
        is_serving=True
    ).exclude(id=new_provider.id).first()

    new_provider.is_serving = True
    new_provider.status = "ready"
    new_provider.save()

    if old_provider:

        EmbeddedObject.objects.filter(
            provider=old_provider
        ).delete()

        old_provider.is_serving = False
        old_provider.save()



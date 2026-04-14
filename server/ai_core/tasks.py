from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import EmbeddingProvider
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

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete
from django.dispatch import receiver

from ai_core.models import EmbeddedObject
from .models import Document


@receiver(post_delete, sender=Document)
def delete_document_embeddings_and_file(sender, instance, **kwargs):
    # Embeddings point at documents through a generic relation, so the
    # database doesn't cascade; leftover chunks would break later searches.
    EmbeddedObject.objects.filter(
        content_type=ContentType.objects.get_for_model(Document),
        object_id=str(instance.pk),
    ).delete()

    if instance.file:
        instance.file.delete(save=False)

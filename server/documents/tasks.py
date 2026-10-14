from celery import shared_task
from django.utils import timezone

from .models import Document
from .services.document_processing_service import DocumentProcessingService, join_segments
from ai_core.services.embedding_service import EmbeddingService


@shared_task
def extract_and_index_document(document_id: int):
    doc = Document.objects.filter(id=document_id).select_related("chat", "user").first()
    if not doc:
        return f"Document {document_id} not found"

    doc.status = Document.StatusChoices.PROCESSING
    doc.save(update_fields=["status"])

    try:
        segments = DocumentProcessingService.extract_segments(doc.file.path)
        text = join_segments(segments)

        if not text.strip():
            doc.status = Document.StatusChoices.FAILED
            doc.save(update_fields=["status"])
            return f"No text extracted for document {document_id}"

        doc.extracted_text = text
        doc.extracted_segments = segments
        doc.updated_at = timezone.now()
        doc.save(update_fields=["extracted_text", "extracted_segments", "updated_at"])

        service = EmbeddingService()

        tag = f"chat:{doc.chat.id}"

        service.embed_instance(doc, text, tag=tag, segments=segments)

        doc.status = Document.StatusChoices.DONE
        doc.save(update_fields=["status"])

        return f"Document {document_id} processed"

    except Exception as e:
        doc.status = Document.StatusChoices.FAILED
        doc.save(update_fields=["status"])
        return str(e)

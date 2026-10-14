"""
Re-extracts and re-embeds uploaded documents, e.g. after changing extraction or
chunk size, so old documents get page-level citations too.

    python manage.py reindex_documents             # every uploaded document
    python manage.py reindex_documents --chat <uuid>
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from ai_core.models import EmbeddedObject
from documents.models import Document
from documents.tasks import extract_and_index_document


class Command(BaseCommand):
    help = "Re-extract and re-embed uploaded documents."

    def add_arguments(self, parser):
        parser.add_argument("--chat", help="Only the documents of this chat (uuid).")

    def handle(self, *args, **opts):
        documents = Document.objects.filter(source_type=Document.SourceTypeChoices.FILE).exclude(file="")
        if opts["chat"]:
            documents = documents.filter(chat__uuid=opts["chat"])

        content_type = ContentType.objects.get_for_model(Document)
        done = failed = 0
        for doc in documents.iterator():
            # Drop the old chunks, then index again with the current pipeline.
            EmbeddedObject.objects.filter(content_type=content_type, object_id=str(doc.pk)).delete()
            message = extract_and_index_document(doc.id)
            doc.refresh_from_db()
            if doc.status == Document.StatusChoices.DONE:
                done += 1
            else:
                failed += 1
                self.stderr.write(f"{doc.original_filename} ({doc.uuid}): {message}")

        self.stdout.write(self.style.SUCCESS(f"Re-indexed {done} documents" + (f", {failed} failed" if failed else "") + "."))

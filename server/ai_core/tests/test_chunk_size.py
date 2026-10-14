from pathlib import Path
from types import SimpleNamespace

from ai_core.services.embedding_service import ChunkingService
from ai_core.services.token_service import TokenService
from documents.services.document_processing_service import DocumentProcessingService

PAPER = Path(__file__).resolve().parents[3] / "eval" / "sources" / "refined.pdf"


def provider(max_tokens):
    return SimpleNamespace(max_input_tokens=lambda: max_tokens, count_tokens=TokenService.count_tokens)


def test_chunks_are_sized_for_retrieval_not_the_embedding_limit(settings):
    settings.RAG_CHUNK_TOKENS, settings.RAG_CHUNK_OVERLAP_TOKENS = 400, 60
    chunker = ChunkingService(provider(8192))

    chunks = chunker.chunk_text(DocumentProcessingService.extract_text(str(PAPER)))

    assert chunker.max_tokens == 400
    assert len(chunks) > 20  # a 12-page paper, not 2 chunks
    assert max(TokenService.count_tokens(c) for c in chunks) <= 400


def test_a_smaller_embedding_limit_still_wins(settings):
    settings.RAG_CHUNK_TOKENS = 400

    assert ChunkingService(provider(256)).max_tokens == 256

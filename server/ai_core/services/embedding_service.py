import re
from typing import List, Optional
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import transaction, connection
from ai_core.embedding_providers.factory import EmbeddingProviderFactory
from ai_core.exceptions import ProviderUnavailable
from ai_core.models import EmbeddedObject, EmbeddingChunk


class ChunkingService:
    """
    Provider-aware recursive semantic chunker with overlap.
    Uses provider tokenizer + max_tokens + overlap to chunk intelligently.
    """

    def __init__(self, provider, overlap_tokens: Optional[int] = None, chunk_tokens: Optional[int] = None):
        self.provider = provider
        # Chunks are sized for retrieval, not by the embedding model's input limit:
        # a few hundred tokens let search return the passage, not half a paper.
        chunk_tokens = chunk_tokens or settings.RAG_CHUNK_TOKENS
        self.max_tokens = min(provider.max_input_tokens(), chunk_tokens)
        self.overlap_tokens = settings.RAG_CHUNK_OVERLAP_TOKENS if overlap_tokens is None else overlap_tokens
        
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be less than max_tokens.")

    def chunk_text(self, text: str) -> List[str]:
        """
        High-quality recursive chunking.
        Splits hierarchically: Paragraph blocks -> Lines -> Sentences -> Words -> Characters.
        """
        if not text:
            return []

        tok_count = self.provider.count_tokens(text)
        if tok_count <= self.max_tokens:
            return [text]

        # 1) Block / Multi-newline split (Semantic Paragraphs)
        blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
        if len(blocks) > 1:
            return self._chunk_list(blocks, joiner="\n\n")

        # 2) Single newline split
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) > 1:
            return self._chunk_list(lines, joiner="\n")

        # 3) Sentence split (keeps punctuation using regex lookbehind)
        # Splits on ".", "!", or "?" followed by a space.
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if len(sentences) > 1:
            return self._chunk_list(sentences, joiner=" ")

        # 4) Word split (if a single sentence is incredibly long)
        words = [w.strip() for w in text.split(" ") if w.strip()]
        if len(words) > 1:
            return self._chunk_list(words, joiner=" ")

        # 5) Fallback: Absolute worst-case scenario, split by characters
        mid = len(text) // 2
        return self.chunk_text(text[:mid]) + self.chunk_text(text[mid:])

    def _chunk_list(self, pieces: List[str], joiner: str = "\n") -> List[str]:
        """
        Combine pieces using a sliding window to respect overlap_tokens.
        """
        chunks = []
        buffer = []
        buffer_tokens = 0
        joiner_tokens = self.provider.count_tokens(joiner) if joiner else 0

        for piece in pieces:
            piece_tokens = self.provider.count_tokens(piece)
            
            additional_tokens = piece_tokens + (joiner_tokens if buffer else 0)

            if buffer and buffer_tokens + additional_tokens > self.max_tokens:
                chunks.append(joiner.join(buffer))
                
                new_buffer = []
                new_buffer_tokens = 0
                
                for prev_piece in reversed(buffer):
                    prev_piece_tokens = self.provider.count_tokens(prev_piece)
                    cost = prev_piece_tokens + (joiner_tokens if new_buffer else 0)
                    
                    if new_buffer_tokens + cost <= self.overlap_tokens:
                        new_buffer.insert(0, prev_piece)
                        new_buffer_tokens += cost
                    else:
                        break
                
                buffer = new_buffer
                buffer_tokens = new_buffer_tokens
                
                buffer.append(piece)
                buffer_tokens += piece_tokens + (joiner_tokens if buffer else 0)
            else:
                buffer.append(piece)
                buffer_tokens += additional_tokens

        if buffer:
            chunks.append(joiner.join(buffer))

        final_chunks = []
        for ch in chunks:
            if self.provider.count_tokens(ch) > self.max_tokens:
                final_chunks.extend(self.chunk_text(ch))
            else:
                final_chunks.append(ch)

        return final_chunks




class EmbeddingService:
    """
    This is the MAIN high-level interface used across your app.
    You send in: model instance + text
    It handles:
        - chunking
        - embedding
        - storing EmbeddedObject + EmbeddingChunk
        - vector search
    """

    def __init__(self, provider_id: Optional[int] = None):
        try:
            self.provider = EmbeddingProviderFactory.get_provider(provider_id)
        except ProviderUnavailable as exc:
            raise ProviderUnavailable(f"EmbeddingService init failed: {exc}")

        self.chunker = ChunkingService(self.provider)


    @transaction.atomic
    def embed_instance(self, instance, text: str, tag: Optional[str] = None) -> EmbeddedObject:
        """
        Main entry point:
            embed_instance(article, article.body)
        """

        ct = ContentType.objects.get_for_model(instance)

        exists = EmbeddedObject.objects.filter(
            content_type=ct,
            object_id=str(instance.pk),
            provider_id=self.provider.provider_model.id
        ).exists()

        if exists:
            # Provider already embedded this instance → skip
            return None

        eo = EmbeddedObject.objects.create(
            content_type=ct,
            object_id=str(instance.pk),
            provider=self.provider.provider_model,
            tag=tag,
        )

        chunks = self.chunker.chunk_text(text)

        embeddings = self.embed_documents(chunks)

        chunk_records = []
        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            chunk_records.append(
                EmbeddingChunk(
                    embedded_object=eo,
                    text=chunk_text,
                    embedding=emb,
                    chunk_index=idx,
                    token_count=self.provider.count_tokens(chunk_text),
                )
            )

        EmbeddingChunk.objects.bulk_create(chunk_records)

        return eo

    # LOW-LEVEL embedding API

    def embed_query(self, text: str):
        return self.provider.embed_query(text)

    def embed_documents(self, texts: List[str], batch_size: int = 32):
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embs = self.provider.embed_documents(batch)
            results.extend(embs)
        return results

    def search(self, query: str, content_model=None, limit: int = 5, tag: Optional[str] = None):
        """
        Vector search using pgvector.
        Returns:
            List of tuples: (instance, score, text)
        """
        query_vec = self.embed_query(query)
        params = [query_vec]


        base_sql = """
            SELECT
                eo.content_type_id,
                eo.object_id,
                1 - (c.embedding <=> %s::vector) AS score,
                c.text
            FROM ai_core_embeddingchunk c
        """
        
        join_sql = " INNER JOIN ai_core_embeddedobject eo ON eo.id = c.embedded_object_id "

        # Only compare against vectors from the model that embedded the query;
        # during a provider switch, chunks from two models coexist.
        where_clauses = ["eo.provider_id = %s"]
        params.append(self.provider.provider_model.id)

        # Optional filtering by model type
        if content_model:
            ct = ContentType.objects.get_for_model(content_model)
            where_clauses.append("eo.content_type_id = %s")
            params.append(ct.id)

        # Optional tag filter
        if tag:
            where_clauses.append("eo.tag = %s")
            params.append(tag)
        
        # Assemble the full query
        query_sql = base_sql + join_sql
        if where_clauses:
            query_sql += " WHERE " + " AND ".join(where_clauses)

        query_sql += " ORDER BY score DESC LIMIT %s;"
        params.append(limit)

        with connection.cursor() as cur:
            cur.execute(query_sql, params)
            rows = cur.fetchall()

        # Load the matched objects with one query per content type, not two per row.
        ids_by_type = {}
        for ct_id, object_id, _, _ in rows:
            ids_by_type.setdefault(ct_id, set()).add(object_id)

        objects = {}
        for ct_id, ids in ids_by_type.items():
            model = ContentType.objects.get_for_id(ct_id).model_class()
            for obj in model._default_manager.filter(pk__in=ids):
                objects[(ct_id, str(obj.pk))] = obj

        results = []
        for ct_id, object_id, score, text in rows:
            obj = objects.get((ct_id, object_id))
            if obj is not None:  # the source was deleted since it was embedded
                results.append((obj, score, text))


        return results

    # Metadata

    @property
    def provider_type(self):
        return self.provider.provider_model.provider_type

    @property
    def provider_name(self):
        return self.provider.provider_model.name

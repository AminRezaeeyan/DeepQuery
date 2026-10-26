import math
import re
from collections import Counter
from typing import List, Optional
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import transaction, connection
from ai_core.embedding_providers.factory import EmbeddingProviderFactory
from ai_core.exceptions import ProviderUnavailable
from ai_core.models import EmbeddedObject, EmbeddingChunk

# Keyword search ranks a scope's chunks in memory; above this many it's skipped.
KEYWORD_SCAN_LIMIT = 5000
RRF_K = 60
# Arabic letter forms that Persian text also uses, folded so either spelling matches.
LETTER_FOLDS = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ة": "ه"})


def words(text: str) -> list[str]:
    # \w is Unicode-aware, so Persian words are kept; the zero-width non-joiner splits
    # compounds the same way in queries and passages.
    return re.findall(r"\w+", text.lower().translate(LETTER_FOLDS))


def bm25_rank(query: str, texts: list[str], k1: float = 1.5, b: float = 0.75) -> list[tuple[int, float]]:
    """(index, score) of the texts that share words with the query, best first."""
    terms = set(words(query))
    docs = [Counter(words(t)) for t in texts]
    if not terms or not docs:
        return []
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths) / len(docs) or 1
    # Rare words count for more, so "inter-annotator" outweighs "the" and "dataset".
    idf = {t: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5)) for t in terms for n in [sum(t in d for d in docs)]}
    scores = []
    for i, (doc, length) in enumerate(zip(docs, lengths)):
        score = sum(
            idf[t] * doc[t] * (k1 + 1) / (doc[t] + k1 * (1 - b + b * length / average))
            for t in terms if doc[t]
        )
        if score > 0:
            scores.append((i, score))
    return sorted(scores, key=lambda item: -item[1])


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
    def embed_instance(self, instance, text: str, tag: Optional[str] = None, segments: Optional[list] = None) -> EmbeddedObject:
        """
        Main entry point:
            embed_instance(article, article.body)

        With `segments` ([{"label": "p. 3", "text": ...}]), each part is chunked on
        its own and its chunks remember the label, so citations can name the page.
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

        parts = segments or [{"label": None, "text": text}]
        chunks = [
            (chunk, part.get("label") or "")
            for part in parts
            for chunk in self.chunker.chunk_text(part["text"])
        ]

        embeddings = self.embed_documents([chunk for chunk, _ in chunks])

        chunk_records = []
        for idx, ((chunk_text, location), emb) in enumerate(zip(chunks, embeddings)):
            chunk_records.append(
                EmbeddingChunk(
                    embedded_object=eo,
                    text=chunk_text,
                    embedding=emb,
                    chunk_index=idx,
                    location=location,
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
            List of tuples: (instance, score, text, location)
        """
        where_sql, params = self._filters(content_model, tag)
        query_sql = f"""
            SELECT eo.content_type_id, eo.object_id, 1 - (c.embedding <=> %s::vector) AS score, c.text, c.location
            FROM ai_core_embeddingchunk c
            INNER JOIN ai_core_embeddedobject eo ON eo.id = c.embedded_object_id
            WHERE {where_sql}
            ORDER BY score DESC LIMIT %s;
        """
        with connection.cursor() as cur:
            cur.execute(query_sql, [self.embed_query(query), *params, limit])
            rows = cur.fetchall()
        return self._with_objects(rows)

    def keyword_search(self, query: str, content_model=None, limit: int = 5, tag: Optional[str] = None):
        """BM25 over the matching chunks' words; scores aren't comparable to search()'s."""
        where_sql, params = self._filters(content_model, tag)
        with connection.cursor() as cur:
            cur.execute(f"""
                SELECT eo.content_type_id, eo.object_id, c.text, c.location
                FROM ai_core_embeddingchunk c
                INNER JOIN ai_core_embeddedobject eo ON eo.id = c.embedded_object_id
                WHERE {where_sql}
                LIMIT %s;
            """, [*params, KEYWORD_SCAN_LIMIT + 1])
            rows = cur.fetchall()
        if len(rows) > KEYWORD_SCAN_LIMIT:  # too many to rank in memory; vectors alone will do
            return []
        ranked = bm25_rank(query, [text for _, _, text, _ in rows])[:limit]
        return self._with_objects([(rows[i][0], rows[i][1], score, rows[i][2], rows[i][3]) for i, score in ranked])

    def hybrid_search(self, query: str, content_model=None, limit: int = 5, tag: Optional[str] = None):
        """
        Vector and keyword results merged by reciprocal rank fusion. Vectors find
        passages that mean the same thing; keywords find the exact names, numbers
        and terms a passage contains even when the rest of it (a figure caption,
        a neighbouring table) pulls its vector elsewhere.
        """
        pool = max(limit * 4, 20)
        fused = {}
        for results in (self.search(query, content_model, pool, tag), self.keyword_search(query, content_model, pool, tag)):
            for rank, (obj, _, text, location) in enumerate(results):
                key = (type(obj), obj.pk, location, text)
                score = fused.get(key, (obj, 0.0))[1] + 1 / (RRF_K + rank + 1)
                fused[key] = (obj, score)
        best = sorted(fused.items(), key=lambda item: -item[1][1])[:limit]
        return [(obj, score, text, location) for (_, _, location, text), (obj, score) in best]

    def _filters(self, content_model, tag):
        # Only compare against vectors from the model that embedded the query;
        # during a provider switch, chunks from two models coexist.
        clauses, params = ["eo.provider_id = %s"], [self.provider.provider_model.id]
        if content_model:
            clauses.append("eo.content_type_id = %s")
            params.append(ContentType.objects.get_for_model(content_model).id)
        if tag:
            clauses.append("eo.tag = %s")
            params.append(tag)
        return " AND ".join(clauses), params

    @staticmethod
    def _with_objects(rows):
        """(content type, object id, score, text, location) rows → (instance, score, text, location)."""
        # Load the matched objects with one query per content type, not two per row.
        ids_by_type = {}
        for ct_id, object_id, _, _, _ in rows:
            ids_by_type.setdefault(ct_id, set()).add(object_id)

        objects = {}
        for ct_id, ids in ids_by_type.items():
            model = ContentType.objects.get_for_id(ct_id).model_class()
            for obj in model._default_manager.filter(pk__in=ids):
                objects[(ct_id, str(obj.pk))] = obj

        results = []
        for ct_id, object_id, score, text, location in rows:
            obj = objects.get((ct_id, object_id))
            if obj is not None:  # the source was deleted since it was embedded
                results.append((obj, score, text, location))
        return results

    # Metadata

    @property
    def provider_type(self):
        return self.provider.provider_model.provider_type

    @property
    def provider_name(self):
        return self.provider.provider_model.name

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_core.embedding_providers.gemini_provider import GeminiEmbeddingProvider
from ai_core.embedding_providers.hf_local_provider import HFLocalEmbeddingProvider


def provider_model(**overrides):
    values = {
        "model_name": "org/model",
        "provider_type": "x",
        "api_key": "key",
        "max_tokens": 512,
        "dimension": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestGeminiEmbeddingProvider:

    def _provider(self):
        with patch("ai_core.embedding_providers.gemini_provider.genai.Client") as client_cls:
            provider = GeminiEmbeddingProvider(provider_model(model_name="gemini-embedding-001"))
        embed = client_cls.return_value.models.embed_content
        embed.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3]), SimpleNamespace(values=[0.4, 0.5, 0.6])]
        )
        return provider, embed

    def test_embeds_documents_with_the_current_sdk(self):
        provider, embed = self._provider()

        vectors = provider.embed_documents(["a", "b"])

        assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        kwargs = embed.call_args.kwargs
        assert kwargs["model"] == "gemini-embedding-001"
        assert kwargs["contents"] == ["a", "b"]
        assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
        assert kwargs["config"].output_dimensionality == 3

    def test_embeds_queries_as_retrieval_queries(self):
        provider, embed = self._provider()

        assert provider.embed_query("q") == [0.1, 0.2, 0.3]
        assert embed.call_args.kwargs["config"].task_type == "RETRIEVAL_QUERY"


class TestHFLocalEmbeddingProvider:

    def _provider(self):
        with patch("transformers.AutoTokenizer.from_pretrained"):
            return HFLocalEmbeddingProvider(provider_model(model_name="org/model"))

    def test_model_path_uses_the_provider_model(self):
        assert self._provider().model_path.endswith("org--model")

    def test_embeds_with_a_loaded_model(self):
        provider = self._provider()
        model = MagicMock()
        model.encode.return_value = MagicMock(tolist=lambda: [[1.0, 2.0]])

        with patch("sentence_transformers.SentenceTransformer", return_value=model), \
             patch.dict("ai_core.embedding_providers.hf_local_provider._loaded_models", clear=True):
            assert provider.embed_query("text") == [1.0, 2.0]

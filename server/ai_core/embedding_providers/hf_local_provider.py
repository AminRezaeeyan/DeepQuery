import os
from threading import Lock
from sentence_transformers import SentenceTransformer
from django.conf import settings
from .base import EmbeddingProviderBase, register_embedding_provider

# Storage for loaded models to avoid memory overhead
_loaded_models = {}
_load_lock = Lock()


@register_embedding_provider("hf_local")
class HFLocalEmbeddingProvider(EmbeddingProviderBase):
    def __init__(self, provider_model):
        super().__init__(provider_model)
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

    @property
    def model_path(self):
        """Determines the local path where the model is stored."""
        models_dir = os.path.join(settings.BASE_DIR, "media", "models", "embeddings")
        os.makedirs(models_dir, exist_ok=True)
        safe_name = self.provider_config.model_name.replace("/", "--")
        return os.path.join(models_dir, safe_name)

    def _get_model(self):
        """Thread-safe singleton loader for the model."""
        model_name = self.provider_config.model_name
        
        if model_name not in _loaded_models:
            with _load_lock:
                if model_name not in _loaded_models:
                    _loaded_models[model_name] = SentenceTransformer(
                        self.model_path, 
                        device="cpu"  # Force CPU for stability in web workers
                    )
        return _loaded_models[model_name]

    def embed_documents(self, texts):
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def is_available(self):
        """Checks if the model directory exists and is not empty."""
        return os.path.exists(self.model_path) and len(os.listdir(self.model_path)) > 0

    def download_model(self):
        """Method to be called by a Celery task to perform the initial download."""
        model = SentenceTransformer(self.provider_config.model_name)
        model.save(self.model_path)

    def count_tokens(self, text):
        return len(self.tokenizer.encode(text))

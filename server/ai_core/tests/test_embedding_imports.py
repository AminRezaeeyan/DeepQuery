import importlib
import sys
from unittest.mock import patch


def test_hf_local_provider_imports_without_sentence_transformers():
    """The factory imports every provider module, so an optional dependency
    must not be imported at module level."""
    module_name = "ai_core.embedding_providers.hf_local_provider"
    sys.modules.pop(module_name, None)

    with patch.dict(sys.modules, {"sentence_transformers": None}):
        module = importlib.import_module(module_name)

    assert hasattr(module, "HFLocalEmbeddingProvider")

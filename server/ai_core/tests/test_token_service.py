import importlib
import sys
from unittest.mock import patch


def test_importing_token_service_does_not_load_the_tokenizer():
    """The app must start without network access to tiktoken's download host."""
    sys.modules.pop("ai_core.services.token_service", None)

    with patch("tiktoken.get_encoding") as get_encoding:
        importlib.import_module("ai_core.services.token_service")

    get_encoding.assert_not_called()


def test_count_tokens_loads_the_tokenizer_on_first_use():
    from ai_core.services.token_service import TokenService

    assert TokenService.count_tokens("") == 0
    assert TokenService.count_tokens("hello world") > 0

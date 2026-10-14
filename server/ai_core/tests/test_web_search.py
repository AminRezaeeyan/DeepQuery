from unittest.mock import patch

from ai_core.services.web_search_service import WebSearchService


def test_search_uses_ddgs_with_the_configured_backends(settings):
    settings.WEB_SEARCH_BACKENDS, settings.WEB_SEARCH_TIMEOUT = "duckduckgo,bing", 7
    hits = [{"title": "Fandom", "href": "https://en.wikipedia.org/wiki/Fandom", "body": "Founded 2004"}, {"title": "no link", "href": ""}]

    with patch("ai_core.services.web_search_service.DDGS") as ddgs:
        ddgs.return_value.text.return_value = hits
        results = WebSearchService().search("Wikia founded", max_results=3)

    ddgs.assert_called_once_with(timeout=7)
    ddgs.return_value.text.assert_called_once_with("Wikia founded", max_results=3, backend="duckduckgo,bing")
    assert results == [{"title": "Fandom", "url": "https://en.wikipedia.org/wiki/Fandom", "snippet": "Founded 2004"}]


def test_search_failures_return_no_results():
    with patch("ai_core.services.web_search_service.DDGS") as ddgs:
        ddgs.return_value.text.side_effect = RuntimeError("No results found.")
        assert WebSearchService().search("anything") == []


def test_no_api_key_is_needed(settings):
    # The old Serper setup raised here when its key was missing, breaking every chat.
    assert not hasattr(settings, "SERPER_API_KEY")
    WebSearchService()

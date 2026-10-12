import socket

import pytest
from unittest.mock import MagicMock, patch

from ai_core.services.web_search_service import UnsafeURL, WebKnowledgeService, WebPageFetcher, check_public_url


def resolves_to(*addresses):
    infos = [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 80)) for a in addresses]
    return patch("ai_core.services.web_search_service.socket.getaddrinfo", return_value=infos)


def response(status=200, body=b"<p>hello</p>", headers=None):
    res = MagicMock(status_code=status, encoding="utf-8")
    res.headers = {"Content-Type": "text/html", **(headers or {})}
    res.is_redirect = status in (301, 302, 303, 307, 308)
    res.iter_content.return_value = [body]
    return res


class TestCheckPublicUrl:

    @pytest.mark.parametrize(
        "address",
        ["127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "0.0.0.0", "::1", "fc00::1", "::ffff:127.0.0.1"],
    )
    def test_rejects_hosts_that_resolve_to_internal_addresses(self, address):
        with resolves_to(address), pytest.raises(UnsafeURL):
            check_public_url("http://example.com/")

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://example.com", "http:///nohost"])
    def test_rejects_other_schemes(self, url):
        with pytest.raises(UnsafeURL):
            check_public_url(url)

    def test_accepts_public_hosts(self):
        with resolves_to("93.184.215.14"):
            check_public_url("https://example.com/page")


class TestWebPageFetcher:

    def test_internal_url_is_never_requested(self):
        with resolves_to("127.0.0.1"), patch("ai_core.services.web_search_service.requests.get") as get:
            assert WebPageFetcher().fetch("http://localhost:8000/admin/") == ""
        get.assert_not_called()

    def test_redirect_to_an_internal_address_is_blocked(self):
        redirect = response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

        def resolve(host, *args, **kwargs):
            address = "169.254.169.254" if host == "169.254.169.254" else "93.184.215.14"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))]

        with patch("ai_core.services.web_search_service.socket.getaddrinfo", side_effect=resolve), \
             patch("ai_core.services.web_search_service.requests.get", return_value=redirect) as get:
            assert WebPageFetcher().fetch("http://example.com/") == ""
        assert get.call_count == 1

    def test_reads_at_most_max_bytes(self):
        big = response(body=b"a" * (WebPageFetcher.MAX_BYTES + 10))
        big.iter_content.return_value = [b"<p>" + b"a" * 1000 + b"</p>"] * 3000

        with resolves_to("93.184.215.14"), patch("ai_core.services.web_search_service.requests.get", return_value=big):
            text = WebPageFetcher().fetch("http://example.com/")

        assert len(text) <= 20000

    def test_fetches_a_public_page(self):
        with resolves_to("93.184.215.14"), patch("ai_core.services.web_search_service.requests.get", return_value=response()) as get:
            assert WebPageFetcher().fetch("http://example.com/").strip() == "hello"
        assert get.call_args.kwargs["timeout"]


class TestUrlsFromPrompt:

    def test_a_prompt_cannot_trigger_more_than_a_few_fetches(self):
        prompt = " ".join(f"https://site{i}.example.com" for i in range(20))

        with patch("ai_core.services.web_search_service.EmbeddingService"), \
             patch("ai_core.services.web_search_service.WebSearchQueryGenerator"), \
             patch("ai_core.services.web_search_service.WebSearchService"), \
             patch.object(WebPageFetcher, "fetch", return_value="") as fetch:
            WebKnowledgeService(chat=1, user=1).gather_and_embed(prompt)

        assert fetch.call_count == WebKnowledgeService.MAX_SEARCH_RESULTS

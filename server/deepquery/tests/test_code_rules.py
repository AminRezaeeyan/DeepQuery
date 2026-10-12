"""Checks for the code rules in CLAUDE.md that are easy to break by accident."""
import ast
from pathlib import Path
from unittest.mock import patch

import requests

SERVER = Path(__file__).resolve().parents[2]
HTTP_CLIENTS = {"OpenAI", "Anthropic", "Client"}  # Client = google.genai.Client


def app_sources():
    for path in SERVER.rglob("*.py"):
        parts = path.relative_to(SERVER).parts
        if "tests" in parts or "migrations" in parts or parts[0] in {"venv", ".venv"} or path.name == "conftest.py":
            continue
        yield path, ast.parse(path.read_text(), filename=str(path))


def calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            owner = getattr(func.value, "id", None) if isinstance(func, ast.Attribute) else None
            yield node, name, owner, {kw.arg for kw in node.keywords}


def test_no_print_calls():
    found = [f"{path}:{node.lineno}" for path, tree in app_sources() for node, name, owner, _ in calls(tree) if name == "print" and owner is None]
    assert found == [], "use logging instead of print"


def test_outgoing_http_calls_have_timeouts():
    missing = []
    for path, tree in app_sources():
        for node, name, owner, kwargs in calls(tree):
            if owner == "requests" and name in {"get", "post", "put", "delete", "request"} and "timeout" not in kwargs:
                missing.append(f"{path}:{node.lineno}")
            if name in HTTP_CLIENTS and not kwargs & {"timeout", "http_options"}:
                missing.append(f"{path}:{node.lineno}")
    assert missing == []


def test_zarinpal_requests_have_a_timeout(settings):
    from subscriptions.services import get_zarinpal

    with patch.object(requests.Session, "request") as request:
        zarinpal = get_zarinpal()
        zarinpal.http_client.post("https://example.com", json={})
        zarinpal.graphql_client.post("https://example.com", json={})

    assert all(call.kwargs.get("timeout") for call in request.call_args_list)
    assert request.call_count == 2

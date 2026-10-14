import shutil
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from ai_core.agent.sandbox import run_python
from ai_core.agent.tools import ToolContext, run_tool, tool_definitions
from chats.models import Chat
from documents.models import Document

SERVER = Path(__file__).resolve().parents[2]
needs_bwrap = pytest.mark.skipif(not shutil.which("bwrap"), reason="bubblewrap isn't installed")


@pytest.fixture(params=["subprocess", pytest.param("bwrap", marks=needs_bwrap)])
def mode(request, settings):
    settings.CODE_SANDBOX = request.param
    return request.param


def test_runs_code_with_the_files_it_was_given(mode, tmp_path):
    data = tmp_path / "runs.csv"
    data.write_text("system,f1\nReFinED,92.77\nBLINK,86.95\n")

    result = run_python("import pandas as pd\nprint(pd.read_csv('runs.csv').f1.max())", [("runs.csv", str(data))])

    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == "92.77"


def test_given_files_are_read_only(mode, tmp_path):
    data = tmp_path / "notes.md"
    data.write_text("x")

    result = run_python("open('notes.md', 'w').write('changed')", [("notes.md", str(data))])

    assert result.exit_code != 0 and "Permission" in result.stderr
    assert data.read_text() == "x"


def test_runaway_code_is_stopped(mode):
    result = run_python("while True:\n    pass", [], timeout=2)

    assert result.timed_out


def test_the_network_is_blocked(mode):
    result = run_python("import socket\nsocket.create_connection(('1.1.1.1', 80), timeout=3)\nprint('connected')", [])

    assert "connected" not in result.stdout
    assert result.exit_code != 0


def test_the_environment_is_empty(mode, monkeypatch):
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "secret-value")

    result = run_python("import os\nprint(sorted(os.environ))", [])

    assert "FIELD_ENCRYPTION_KEY" not in result.stdout


@needs_bwrap
def test_with_bubblewrap_the_server_files_are_invisible(settings):
    settings.CODE_SANDBOX = "bwrap"

    result = run_python(f"print(open({str(SERVER / 'manage.py')!r}).read()[:20])", [])

    assert result.exit_code != 0 and "No such file" in result.stderr


def test_turning_it_off_removes_the_tool(settings):
    settings.CODE_SANDBOX = "off"

    assert "run_python" not in {t["name"] for t in tool_definitions()}
    assert "turned off" in run_python("print(1)", []).stderr


@pytest.mark.django_db
def test_the_tool_offers_the_chats_files_and_numbers_them_for_citation(settings, tmp_path):
    settings.CODE_SANDBOX, settings.MEDIA_ROOT = "subprocess", tmp_path
    user = get_user_model().objects.create_user(email="code@example.com", password="violet-harbor-71")
    chat = Chat.objects.create(user=user, title="Audit")
    Document.objects.create(chat=chat, user=user, original_filename="nil_audit.csv", status="done",
                            file=SimpleUploadedFile("nil_audit.csv", b"gold,cross_pred\nNIL,NIL\nQ1,NIL\n"))
    context = ToolContext(chat_id=chat.id, user_id=user.id)

    output = run_tool("run_python", {"code": "import pandas as pd\ndf = pd.read_csv('nil_audit.csv')\nprint((df.gold == df.cross_pred).mean())"}, context)

    assert "(exit code 0)" in output.text
    assert "[1] nil_audit.csv" in output.text
    assert "stdout:\n0.5" in output.text
    assert output.summary == "Ran Python (3 lines)"

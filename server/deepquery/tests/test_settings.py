from deepquery.settings import csv_list


class TestCsvList:

    def test_empty_value_gives_empty_list(self):
        # Django only allows localhost in DEBUG when ALLOWED_HOSTS is truly empty.
        assert csv_list("") == []

    def test_strips_whitespace_and_drops_blank_entries(self):
        assert csv_list(" a.com , ,b.com,") == ["a.com", "b.com"]


def test_upload_and_static_folders_come_from_the_environment(monkeypatch, tmp_path):
    import importlib
    import deepquery.settings as settings_module

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STATIC_ROOT", str(tmp_path / "static"))
    try:
        reloaded = importlib.reload(settings_module)
        assert reloaded.MEDIA_ROOT == tmp_path / "media"
        assert reloaded.STATIC_ROOT == tmp_path / "static"
    finally:
        monkeypatch.undo()
        importlib.reload(settings_module)

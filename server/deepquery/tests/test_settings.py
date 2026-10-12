from deepquery.settings import csv_list


class TestCsvList:

    def test_empty_value_gives_empty_list(self):
        # Django only allows localhost in DEBUG when ALLOWED_HOSTS is truly empty.
        assert csv_list("") == []

    def test_strips_whitespace_and_drops_blank_entries(self):
        assert csv_list(" a.com , ,b.com,") == ["a.com", "b.com"]

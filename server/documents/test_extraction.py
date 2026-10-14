from pathlib import Path

import pandas as pd

from documents.services.document_processing_service import DocumentProcessingService, clean_pdf_text

PAPER = Path(__file__).resolve().parents[2] / "eval" / "sources" / "refined.pdf"


def test_pdf_text_keeps_the_spaces_between_words():
    text = DocumentProcessingService.extract_text(str(PAPER))

    assert "The largest public EL dataset" in text
    assert "ThelargestpublicELdataset" not in text


def test_pdf_pages_are_labelled_for_citations():
    segments = DocumentProcessingService.extract_segments(str(PAPER))

    table5 = next(s for s in segments if "ReFinED 15 89.4" in s["text"])
    assert table5["label"] == "p. 6"
    assert segments[0]["label"] == "p. 1"


def test_words_broken_across_lines_are_joined():
    assert clean_pdf_text("the model performs men￾tion detection\r\nnext") == "the model performs mention detection\nnext"


def test_every_spreadsheet_sheet_is_read(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as xl:
        pd.DataFrame({"run": ["R1"], "f1": [91.5]}).to_excel(xl, sheet_name="runs", index=False)
        pd.DataFrame({"gpu": ["T4"], "usd_per_hour": [0.53]}).to_excel(xl, sheet_name="prices", index=False)

    segments = DocumentProcessingService.extract_segments(str(path))

    assert [s["label"] for s in segments] == ["sheet: runs", "sheet: prices"]
    assert "0.53" in segments[1]["text"]
    assert "[sheet: prices]" in DocumentProcessingService.extract_text(str(path))


def test_text_files_are_one_unlabelled_segment(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# یادداشت\nمتن فارسی")

    assert DocumentProcessingService.extract_segments(str(path)) == [{"label": None, "text": "# یادداشت\nمتن فارسی"}]

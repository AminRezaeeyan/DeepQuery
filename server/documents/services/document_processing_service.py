import os
from typing import ClassVar

import pandas as pd
import pypdfium2 as pdfium


class DocumentProcessingService:
    """
    Handles document text extraction and file format rules.
    """

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".pdf",
        ".csv",
        ".xlsx",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".json",
        ".md",
    }

    @classmethod
    def normalize_extension(cls, filename: str) -> str:
        return os.path.splitext(filename)[1].lower()

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        return cls.normalize_extension(filename) in cls.SUPPORTED_EXTENSIONS

    TEXT_EXTENSIONS: ClassVar[set[str]] = {".txt", ".csv", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".json", ".md"}

    @classmethod
    def content_matches_extension(cls, uploaded_file) -> bool:
        """Checks the file's first bytes, not just its name."""
        ext = cls.normalize_extension(uploaded_file.name)
        uploaded_file.seek(0)
        head = uploaded_file.read(8192)
        uploaded_file.seek(0)

        if ext == ".pdf":
            return head.startswith(b"%PDF-")
        if ext == ".xlsx":
            return head.startswith(b"PK\x03\x04")  # xlsx is a zip archive
        if ext in cls.TEXT_EXTENSIONS:
            if b"\x00" in head:
                return False
            try:
                head.decode("utf-8")
            except UnicodeDecodeError as e:
                # The read may have cut a multi-byte character in half.
                return e.start >= len(head) - 3
            return True
        return False

    @classmethod
    def extract_segments(cls, file_path: str) -> list[dict]:
        """
        The document's text in labelled parts: one per PDF page ("p. 3"), one per
        spreadsheet sheet ("sheet: prices"), or a single unlabelled part. Labels end
        up in citations, so readers can find the passage.
        """
        ext = cls.normalize_extension(file_path)

        if ext == ".pdf":
            segments = cls._extract_pdf(file_path)
        elif ext == ".csv":
            segments = [{"label": None, "text": cls._extract_csv(file_path)}]
        elif ext == ".xlsx":
            segments = cls._extract_excel(file_path)
        elif ext in cls.TEXT_EXTENSIONS:
            segments = [{"label": None, "text": cls._extract_plain_like(file_path)}]
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        return [seg for seg in segments if seg["text"].strip()]

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        return join_segments(cls.extract_segments(file_path))

    @staticmethod
    def _extract_pdf(file_path: str) -> list[dict]:
        # pdfium keeps the spaces between words that pdfplumber dropped in
        # two-column papers ("ThelargestpublicELdataset").
        pdf = pdfium.PdfDocument(file_path)
        try:
            segments = []
            for number in range(len(pdf)):
                page = pdf[number]
                text = page.get_textpage().get_text_range()
                segments.append({"label": f"p. {number + 1}", "text": clean_pdf_text(text)})
            return segments
        finally:
            pdf.close()

    @staticmethod
    def _extract_csv(file_path: str) -> str:
        df = pd.read_csv(file_path)
        # ensure rows separated with newline and columns with some spacing
        return df.to_string(index=False)

    @staticmethod
    def _extract_excel(file_path: str) -> list[dict]:
        # Every sheet: prices and notes often live outside the first one.
        sheets = pd.read_excel(file_path, sheet_name=None)
        return [{"label": f"sheet: {name}", "text": df.to_string(index=False)} for name, df in sheets.items()]

    @staticmethod
    def _extract_plain_like(file_path: str) -> str:
        # programming languages / text-like: preserve line breaks
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def clean_pdf_text(text: str) -> str:
    # pdfium marks a word broken across lines with U+FFFE ("men\ufffetion").
    text = text.replace("\ufffe", "").replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def join_segments(segments: list[dict]) -> str:
    """One text for display and search, with each labelled part under its label."""
    return "\n\n".join(f"[{seg['label']}]\n{seg['text']}" if seg["label"] else seg["text"] for seg in segments)

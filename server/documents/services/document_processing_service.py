import os
from typing import ClassVar

import pdfplumber
import pandas as pd


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
    def extract_text(cls, file_path: str) -> str:
        ext = cls.normalize_extension(file_path)

        # NOTE: We deliberately insert \n\n between logical units
        # so downstream chunking has good boundaries.

        if ext == ".pdf":
            return cls._extract_pdf(file_path)

        if ext == ".csv":
            return cls._extract_csv(file_path)

        if ext == ".xlsx":
            return cls._extract_excel(file_path)

        if ext in {".txt", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".json", ".md"}:
            return cls._extract_plain_like(file_path)

        raise ValueError(f"Unsupported file format: {ext}")


    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        texts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    texts.append(page_text.strip())
        # separate pages with double newline
        return "\n\n".join(texts)

    @staticmethod
    def _extract_csv(file_path: str) -> str:
        df = pd.read_csv(file_path)
        # ensure rows separated with newline and columns with some spacing
        return df.to_string(index=False)

    @staticmethod
    def _extract_excel(file_path: str) -> str:
        df = pd.read_excel(file_path)
        return df.to_string(index=False)

    @staticmethod
    def _extract_plain_like(file_path: str) -> str:
        # programming languages / text-like: preserve line breaks
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

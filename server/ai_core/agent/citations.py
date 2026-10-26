"""Numbers every source the agent's tools return, so answers can cite them as [n]."""
import re

PAGE = re.compile(r"^p\. \d+$")


class SourceRegistry:
    """
    One citation number per PDF page, and one per file for everything else.

    A page is what a reader needs to check a claim in a long paper. A spreadsheet
    or a text file is small, so splitting it into one number per sheet only makes
    one source look like several; its reference lists the sheets that were read.
    """

    def __init__(self):
        self._sources = {}

    def add(self, key, *, filename=None, url=None, location="") -> int:
        """The citation number for a source, assigning the next one on first sight."""
        location = location or ""
        part = ""
        if key[0] == "doc" and location and not PAGE.match(location):
            key, part, location = key[:2] + ("",), location, ""
        if key not in self._sources:
            self._sources[key] = {
                "cite_id": len(self._sources) + 1,
                "url": url,
                "filename": filename,
                "location": location,
                "parts": [],
            }
        source = self._sources[key]
        if part and part not in source["parts"]:
            source["parts"].append(part)
        source["label"] = self._label(source)
        return source["cite_id"]

    @staticmethod
    def _label(source) -> str:
        name = source["url"] or source["filename"] or "Source"
        if source["location"]:
            return f"{name}, {source['location']}"
        sheets = [p.removeprefix("sheet: ") for p in source["parts"] if p.startswith("sheet: ")]
        return f"{name} (sheets: {', '.join(sheets)})" if sheets else name

    def label(self, cite_id: int) -> str:
        return next(s["label"] for s in self._sources.values() if s["cite_id"] == cite_id)

    def header(self, cite_id: int, location: str = "") -> str:
        """How a tool result introduces a source: the number, and the exact part it shows."""
        source = next(s for s in self._sources.values() if s["cite_id"] == cite_id)
        name = source["url"] or source["filename"] or "Source"
        return f"[{cite_id}] ({name}, {location})" if location else f"[{cite_id}] ({source['label']})"

    def as_citation_map(self) -> dict:
        """Same shape the single-pass pipeline produces, for references and the eval."""
        return dict(self._sources)

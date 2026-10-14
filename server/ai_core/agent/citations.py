"""Numbers every source the agent's tools return, so answers can cite them as [n]."""


class SourceRegistry:
    def __init__(self):
        self._sources = {}

    def add(self, key, *, filename=None, url=None, location="") -> int:
        """The citation number for a source, assigning the next one on first sight."""
        if key not in self._sources:
            name = url or filename or "Source"
            self._sources[key] = {
                "cite_id": len(self._sources) + 1,
                "url": url,
                "filename": filename,
                "location": location or "",
                "label": f"{name}, {location}" if location else name,
            }
        return self._sources[key]["cite_id"]

    def label(self, cite_id: int) -> str:
        return next(s["label"] for s in self._sources.values() if s["cite_id"] == cite_id)

    def as_citation_map(self) -> dict:
        """Same shape the single-pass pipeline produces, for references and the eval."""
        return dict(self._sources)

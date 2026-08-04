from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

FileStatus = Literal["unreviewed", "ok", "error", "needs_review"]
OcrMode = Literal["layout", "pdf_order", "geometric_order"]

VALID_FILE_STATUSES: Final[frozenset[str]] = frozenset(
    {"unreviewed", "ok", "error", "needs_review"}
)
VALID_OCR_MODES: Final[frozenset[str]] = frozenset(
    {"layout", "pdf_order", "geometric_order"}
)


@dataclass(frozen=True, slots=True)
class FileIdentity:
    size: int
    mtime_ns: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScannedPdf:
    file_id: str
    name: str
    path: Path
    identity: FileIdentity

    def to_public_dict(self, manifest_entry: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = manifest_entry or {}
        stored_identity = entry.get("identity") if isinstance(entry, dict) else None
        changed = bool(stored_identity and stored_identity != self.identity.to_dict())
        problem_pages = entry.get("problem_pages", []) if isinstance(entry, dict) else []
        return {
            "file_id": self.file_id,
            "name": self.name,
            "size": self.identity.size,
            "mtime_ns": self.identity.mtime_ns,
            "status": entry.get("status", "unreviewed"),
            "last_page": entry.get("last_page", 0),
            "problem_page_count": len(problem_pages) if isinstance(problem_pages, list) else 0,
            "changed_since_review": changed,
        }


@dataclass(frozen=True, slots=True)
class PageMetadata:
    page_index: int
    width: float
    height: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)

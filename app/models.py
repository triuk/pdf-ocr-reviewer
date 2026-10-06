from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

from .review import issue_counts

FileStatus = Literal["unreviewed", "ok", "error", "needs_review"]
OcrMode = Literal["layout", "pdf_order", "geometric_order"]

VALID_FILE_STATUSES: Final[frozenset[str]] = frozenset(
    {"unreviewed", "ok", "error", "needs_review"}
)
VALID_OCR_MODES: Final[frozenset[str]] = frozenset(
    {"layout", "pdf_order", "geometric_order"}
)


def repair_acceptance_state(entry: dict[str, Any], changed: bool = False) -> dict[str, Any]:
    receipt = entry.get("repair_acceptance")
    counts = issue_counts(entry.get("issues", []))
    accepted = bool(receipt and not changed
                    and receipt["ocr_sha256"] == entry.get("ocr_sha256")
                    and entry.get("review_complete", entry.get("status") == "ok")
                    and not (counts["open"] or counts["fixed"]))
    return {"repairs_accepted": accepted,
            "repair_accepted_at": receipt["accepted_at"] if accepted else None}


@dataclass(frozen=True, slots=True)
class FileIdentity:
    size: int
    mtime_ns: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def to_token(self) -> str:
        # Nanosecond timestamps exceed JavaScript integer precision.
        return f"{self.size}:{self.mtime_ns}"


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
            "identity_token": self.identity.to_token(),
            "status": entry.get("status", "unreviewed"),
            "review_complete": entry.get("review_complete", entry.get("status") == "ok"),
            "last_page": entry.get("last_page", 0),
            "problem_page_count": len(problem_pages) if isinstance(problem_pages, list) else 0,
            "changed_since_review": changed,
            "issue_counts": issue_counts(entry.get("issues", [])),
            **repair_acceptance_state(entry, changed),
        }


@dataclass(frozen=True, slots=True)
class PageMetadata:
    page_index: int
    width: float
    height: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)

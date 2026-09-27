from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import VALID_FILE_STATUSES, VALID_OCR_MODES, ScannedPdf
from .review import ISSUE_KINDS, file_sha256, repair_instructions, validate_issue

MANIFEST_FILENAME = "pdf-ocr-reviewer.manifest.json"
SCHEMA_VERSION = 2


class ManifestError(RuntimeError):
    """Base error for manifest operations."""


class ManifestFormatError(ManifestError):
    """Raised when a manifest is syntactically or structurally invalid."""


class ManifestWriteError(ManifestError):
    """Raised when an atomic manifest write fails."""


def manifest_revision(folder: Path) -> str | None:
    try:
        return file_sha256(folder / MANIFEST_FILENAME)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ManifestError(f"Manifest cannot be read: {exc}") from exc


def default_manifest() -> dict[str, Any]:
    return {
        "repair_instructions": repair_instructions(),
        "schema_version": SCHEMA_VERSION,
        "application": "pdf-ocr-reviewer",
        "updated_at": None,
        "ui": {
            "last_file": None,
            "zoom_percent": 100,
            "ocr_mode": "pdf_order",
            "overlay": True,
            "status_filter": "all",
            "name_filter": "",
            "auto_advance": True,
            "issue_kind": "position",
        },
        "files": {},
    }


def load_manifest(folder: Path) -> dict[str, Any]:
    path = folder / MANIFEST_FILENAME
    if not path.exists():
        return default_manifest()

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ManifestFormatError(f"Manifest is not valid JSON: {path}") from exc
    except OSError as exc:
        raise ManifestError(f"Manifest cannot be read: {path}") from exc

    data = migrate_manifest(data)
    validate_manifest(data)
    return data


def migrate_manifest(data: Any) -> Any:
    if isinstance(data, dict) and data.get("schema_version") == 1:
        data = copy.deepcopy(data)
        data["schema_version"] = SCHEMA_VERSION
        data.setdefault("repair_instructions", repair_instructions())
        files = data.get("files")
        if isinstance(files, dict):
            for entry in files.values():
                if isinstance(entry, dict):
                    entry.setdefault("issues", [])
    # Keep the stored kind key compatible; broaden only the old built-in wording.
    if isinstance(data, dict):
        instructions = data.get("repair_instructions")
        kinds = instructions.get("kinds") if isinstance(instructions, dict) else None
        if isinstance(kinds, dict) and kinds.get("oversized") == "Příliš velký box":
            data = copy.deepcopy(data)
            data["repair_instructions"]["kinds"]["oversized"] = "Špatná velikost boxu"
            data["repair_instructions"].setdefault("kind_notes", repair_instructions()["kind_notes"])
    return data


def validate_manifest(data: Any) -> None:
    if not isinstance(data, dict):
        raise ManifestFormatError("Manifest root must be an object.")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ManifestFormatError(
            f"Unsupported manifest schema version: {data.get('schema_version')!r}"
        )
    if data.get("application") != "pdf-ocr-reviewer":
        raise ManifestFormatError("Manifest belongs to a different application.")
    if not isinstance(data.get("repair_instructions"), dict):
        raise ManifestFormatError("repair_instructions must be an object.")

    ui = data.get("ui")
    files = data.get("files")
    if not isinstance(ui, dict) or not isinstance(files, dict):
        raise ManifestFormatError("Manifest must contain object fields 'ui' and 'files'.")

    zoom = ui.get("zoom_percent", 100)
    if not isinstance(zoom, int) or not 25 <= zoom <= 400:
        raise ManifestFormatError("ui.zoom_percent must be an integer from 25 to 400.")
    if ui.get("ocr_mode", "pdf_order") not in VALID_OCR_MODES:
        raise ManifestFormatError("ui.ocr_mode has an unsupported value.")
    if not isinstance(ui.get("overlay", True), bool):
        raise ManifestFormatError("ui.overlay must be a boolean.")
    if not isinstance(ui.get("issue_kind", "position"), str) or ui.get("issue_kind", "position") not in ISSUE_KINDS:
        raise ManifestFormatError("ui.issue_kind has an unsupported value.")

    for file_id, entry in files.items():
        if not isinstance(file_id, str) or not isinstance(entry, dict):
            raise ManifestFormatError("Each files entry must be an object keyed by a string.")
        if entry.get("status", "unreviewed") not in VALID_FILE_STATUSES:
            raise ManifestFormatError(f"Unsupported status for {file_id!r}.")
        if not isinstance(entry.get("problem_pages", []), list) or not all(
            isinstance(value, int) and value >= 0
            for value in entry.get("problem_pages", [])
        ):
            raise ManifestFormatError(f"Invalid problem_pages for {file_id!r}.")
        issues = entry.get("issues", [])
        if not isinstance(issues, list):
            raise ManifestFormatError(f"Invalid issues for {file_id!r}.")
        try:
            seen = set()
            for issue in issues:
                validate_issue(issue)
                if issue["id"] in seen:
                    raise ValueError("Duplicate issue ID.")
                seen.add(issue["id"])
        except ValueError as exc:
            raise ManifestFormatError(f"Invalid issue in {file_id!r}: {exc}") from exc


def ensure_file_entry(manifest: dict[str, Any], pdf: ScannedPdf) -> dict[str, Any]:
    files = manifest.setdefault("files", {})
    entry = files.setdefault(pdf.file_id, {})
    entry.setdefault("identity", pdf.identity.to_dict())
    entry.setdefault("status", "unreviewed")
    entry.setdefault("last_page", 0)
    entry.setdefault("problem_pages", [])
    entry.setdefault("note", "")
    entry.setdefault("reviewed_at", None)
    entry.setdefault("issues", [])
    return entry


def save_manifest(folder: Path, manifest: dict[str, Any]) -> str:
    validate_manifest(manifest)
    data = {"repair_instructions": copy.deepcopy(manifest["repair_instructions"]), **copy.deepcopy(manifest)}
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    target = folder / MANIFEST_FILENAME

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=folder,
            prefix=f".{MANIFEST_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        _fsync_directory(folder)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ManifestWriteError(f"Manifest cannot be written: {target}") from exc

    manifest["updated_at"] = data["updated_at"]
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fsync_directory(folder: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

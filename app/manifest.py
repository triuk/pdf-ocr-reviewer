from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .file_lock import file_lock
from .models import VALID_FILE_STATUSES, VALID_OCR_MODES, ScannedPdf
from .review import ISSUE_KINDS, file_sha256, repair_instructions, migrate_repair_instructions, validate_issue, valid_hash

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
            "issue_filter": "all",
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
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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
    if isinstance(data, dict) and isinstance(data.get("repair_instructions"), dict):
        instructions = data["repair_instructions"]
        if instructions.get("version") in (1, 2):
            data = copy.deepcopy(data)
            data["repair_instructions"] = migrate_repair_instructions(instructions)
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

    def field(value, predicate, path):
        if not predicate(value):
            raise ManifestFormatError(f"Invalid {path}: {value!r}")

    def choice(value, choices):
        return isinstance(value, str) and value in choices

    integer = lambda value: type(value) is int and value >= 0
    string = lambda value: isinstance(value, str)
    nullable_string = lambda value: value is None or isinstance(value, str)
    field(ui.get("zoom_percent", 100), lambda n: type(n) is int and 25 <= n <= 400, "ui.zoom_percent")
    field(ui.get("ocr_mode", "pdf_order"), lambda v: choice(v, VALID_OCR_MODES), "ui.ocr_mode")
    field(ui.get("issue_kind", "position"), lambda v: choice(v, ISSUE_KINDS), "ui.issue_kind")
    field(ui.get("status_filter", "all"), lambda v: choice(v, {*VALID_FILE_STATUSES, "all"}), "ui.status_filter")
    field(ui.get("issue_filter", "all"), lambda v: choice(v, {"all", "active", "open", "fixed"}), "ui.issue_filter")
    for key in ("overlay", "auto_advance"):
        field(ui.get(key, True), lambda v: type(v) is bool, f"ui.{key}")
    field(ui.get("name_filter", ""), string, "ui.name_filter")
    field(ui.get("last_file"), nullable_string, "ui.last_file")
    field(data.get("updated_at"), nullable_string, "updated_at")

    for file_id, entry in files.items():
        path = f"files[{file_id!r}]"
        field(entry, lambda v: isinstance(v, dict), path)
        field(entry.get("status", "unreviewed"), lambda v: choice(v, VALID_FILE_STATUSES), path + ".status")
        field(entry.get("last_page", 0), integer, path + ".last_page")
        field(entry.get("note", ""), string, path + ".note")
        field(entry.get("reviewed_at"), nullable_string, path + ".reviewed_at")
        pages = entry.get("problem_pages", [])
        field(pages, lambda v: isinstance(v, list) and all(integer(n) for n in v), path + ".problem_pages")
        if "identity" in entry:
            identity = entry["identity"]
            field(identity, lambda v: isinstance(v, dict), path + ".identity")
            for key in ("size", "mtime_ns"):
                field(identity.get(key), integer, path + ".identity." + key)
        if "ocr_sha256" in entry:
            field(entry["ocr_sha256"], valid_hash, path + ".ocr_sha256")
        if "resources" in entry:
            resources = entry["resources"]
            field(resources, lambda v: isinstance(v, dict), path + ".resources")
            for key in ("source", "qa2", "qa3"):
                if key in resources:
                    field(resources[key], lambda v: isinstance(v, str) and bool(v), path + ".resources." + key)
        issues = entry.get("issues", [])
        field(issues, lambda v: isinstance(v, list), path + ".issues")
        seen = set()
        for index, issue in enumerate(issues):
            try:
                validate_issue(issue)
                if issue["id"] in seen:
                    raise ValueError("Duplicate issue ID.")
                seen.add(issue["id"])
            except ValueError as exc:
                raise ManifestFormatError(f"Invalid issue at {path}.issues[{index}]: {exc}") from exc


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


def save_manifest(folder: Path, manifest: dict[str, Any], *, expected_revision: str | None) -> str:
    """Compare and replace under a lock shared by all cooperating writers."""
    try:
        with file_lock(folder / f".{MANIFEST_FILENAME}.lock"):
            if manifest_revision(folder) != expected_revision:
                raise ManifestError("Manifest změnil jiný nástroj. Použijte Načíst opravy; novější data nebyla přepsána.")
            return _write_manifest(folder, manifest)
    except OSError as exc:
        raise ManifestWriteError(f"Manifest cannot be locked or written: {exc}") from exc


def _write_manifest(folder: Path, manifest: dict[str, Any]) -> str:
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
        _backup_current(folder)
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


def _backup_current(folder: Path) -> None:
    target = folder / MANIFEST_FILENAME
    if not target.exists():
        return
    raw = target.read_bytes()
    try:
        validate_manifest(migrate_manifest(json.loads(raw)))
    except (ValueError, ManifestError, UnicodeError):
        return  # A broken source must never displace the last valid backup.
    backup_folder = folder / ".pdf-ocr-reviewer-backups"
    backup_folder.mkdir(exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    if not any(backup_folder.glob(f"*-{digest}.json")):
        path = backup_folder / f"{time.time_ns()}-{digest}.json"
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    backups = sorted(backup_folder.glob("[0-9]*-*.json"), reverse=True)
    for path in backups[10:]:
        path.unlink()


def list_backups(folder: Path) -> list[dict]:
    result = []
    for path in sorted((folder / ".pdf-ocr-reviewer-backups").glob("[0-9]*-*.json"), reverse=True):
        try:
            data = migrate_manifest(json.loads(path.read_text(encoding="utf-8")))
            validate_manifest(data)
            result.append({"id": path.name, "updated_at": data.get("updated_at"),
                           "files": len(data["files"]), "issues": sum(len(e.get("issues", [])) for e in data["files"].values())})
        except (OSError, ValueError, ManifestError):
            continue
    return result


def restore_backup(folder: Path, backup_id: str, *, expected_revision: str | None) -> str:
    if not isinstance(backup_id, str) or not re.fullmatch(r"[0-9]+-[a-f0-9]{64}\.json", backup_id):
        raise ManifestError("Invalid backup ID.")
    try:
        with file_lock(folder / f".{MANIFEST_FILENAME}.lock"):
            if manifest_revision(folder) != expected_revision:
                raise ManifestError("Manifest se od výběru zálohy změnil. Načtěte seznam znovu.")
            candidate = migrate_manifest(json.loads((folder / ".pdf-ocr-reviewer-backups" / backup_id).read_text(encoding="utf-8")))
            validate_manifest(candidate)
            target = folder / MANIFEST_FILENAME
            if target.exists():
                # Also preserve a malformed current file when explicitly restoring.
                previous = folder / ".pdf-ocr-reviewer-backups" / "before-restore.json"
                with previous.open("wb") as handle:
                    handle.write(target.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
            return _write_manifest(folder, candidate)
    except (OSError, ValueError) as exc:
        raise ManifestError(f"Zálohu nelze obnovit: {exc}") from exc

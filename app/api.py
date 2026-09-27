from __future__ import annotations

import copy
import csv
import io
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .folder_dialog import FolderDialogError, select_folder
from .folder_scanner import FolderScanError, scan_pdf_folder
from .manifest import (
    ManifestError,
    ensure_file_entry,
    load_manifest,
    manifest_revision,
    save_manifest,
)
from .models import VALID_FILE_STATUSES, VALID_OCR_MODES, FileIdentity, ScannedPdf
from .pdf_document import PdfDocument, PdfDocumentError
from .raw_packet import pack_raw_packet
from .review import ISSUE_KINDS, companion_resources, file_sha256, issue_counts, validate_issue


class BackendApi:
    def __init__(self, initial_folder: Path | None = None):
        self._lock = threading.RLock()
        self.current_folder: Path | None = None
        self.files: dict[str, ScannedPdf] = {}
        self.manifest: dict[str, Any] | None = None
        self.active_file_id: str | None = None
        self.active_document: PdfDocument | None = None
        self.startup_error: dict[str, str] | None = None
        self.persistence_error: dict[str, str] | None = None
        self._manifest_revision: str | None = None
        self._document_sha256: str | None = None
        if initial_folder is not None:
            try:
                self.open_folder(initial_folder)
            except Exception as exc:
                self.startup_error = {
                    "code": "STARTUP_FOLDER_FAILED",
                    "message": str(exc),
                }

    def close(self) -> None:
        with self._lock:
            if self.active_document is not None:
                self.active_document.close()
                self.active_document = None

    def bind(self, window: Any) -> None:
        window.bind("syncStateB", self.sync_state_callback)
        window.bind("selectFolderB", self.select_folder_callback)
        window.bind("openFolderB", self.open_folder_callback)
        window.bind("refreshFolderB", self.refresh_folder_callback)
        window.bind("openDocumentB", self.open_document_callback)
        window.bind("requestPageB", self.request_page_callback)
        window.bind("setFileStatusB", self.set_file_status_callback)
        window.bind("toggleProblemPageB", self.toggle_problem_page_callback)
        window.bind("setLastPageB", self.set_last_page_callback)
        window.bind("setFileNoteB", self.set_file_note_callback)
        window.bind("setUiOptionsB", self.set_ui_options_callback)
        window.bind("exportCsvB", self.export_csv_callback)
        window.bind("addIssueB", self.add_issue_callback)
        window.bind("updateIssueB", self.update_issue_callback)

    def sync_state_callback(self, event: Any) -> None:
        event.return_string(self._ok(self.public_state()))

    def select_folder_callback(self, event: Any) -> None:
        try:
            selected = select_folder(self.current_folder)
            if selected is None:
                event.return_string(self._ok({"cancelled": True}))
                return
            event.return_string(self._ok(self.open_folder(selected)))
        except FolderDialogError as exc:
            event.return_string(self._error("FOLDER_DIALOG_FAILED", str(exc)))
        except (FolderScanError, ManifestError) as exc:
            event.return_string(self._error("FOLDER_OPEN_FAILED", str(exc)))

    def open_folder_callback(self, event: Any) -> None:
        try:
            raw_path = event.get_string().strip()
            event.return_string(self._ok(self.open_folder(Path(raw_path))))
        except (FolderScanError, ManifestError, OSError, ValueError) as exc:
            event.return_string(self._error("FOLDER_OPEN_FAILED", str(exc)))

    def refresh_folder_callback(self, event: Any) -> None:
        if self.current_folder is None:
            event.return_string(self._error("NO_FOLDER", "Open a folder first."))
            return
        try:
            event.return_string(self._ok(self.open_folder(self.current_folder)))
        except (FolderScanError, ManifestError) as exc:
            event.return_string(self._error("FOLDER_REFRESH_FAILED", str(exc)))

    def open_document_callback(self, event: Any) -> None:
        try:
            event.return_string(self._ok(self.open_document(event.get_string())))
        except (PdfDocumentError, KeyError, ManifestError, ValueError, OSError) as exc:
            event.return_string(self._error("PDF_OPEN_FAILED", str(exc)))

    def request_page_callback(self, event: Any) -> None:
        try:
            request_id = event.get_string_at(0)
            file_id = event.get_string_at(1)
            page_index = event.get_int_at(2)
            target_width = event.get_int_at(3)
            packet = self.render_page_packet(request_id, file_id, page_index, target_width)
            if hasattr(event, "send_raw_client"):
                event.send_raw_client("pageReadyF", packet)
            else:
                event.window.send_raw("pageReadyF", packet)
            event.return_string(self._ok({"request_id": request_id, "queued": False}))
        except (PdfDocumentError, KeyError, ValueError, ManifestError, OSError) as exc:
            event.return_string(self._error("PAGE_RENDER_FAILED", str(exc)))

    def set_file_status_callback(self, event: Any) -> None:
        try:
            file_id = event.get_string_at(0)
            status = event.get_string_at(1)
            event.return_string(self._ok(self.set_file_status(file_id, status)))
        except (KeyError, ValueError, ManifestError) as exc:
            event.return_string(self._error("STATUS_SAVE_FAILED", str(exc)))

    def toggle_problem_page_callback(self, event: Any) -> None:
        try:
            file_id = event.get_string_at(0)
            page_index = event.get_int_at(1)
            event.return_string(self._ok(self.toggle_problem_page(file_id, page_index)))
        except (KeyError, ValueError, ManifestError) as exc:
            event.return_string(self._error("PROBLEM_PAGE_SAVE_FAILED", str(exc)))

    def set_last_page_callback(self, event: Any) -> None:
        try:
            file_id = event.get_string_at(0)
            page_index = event.get_int_at(1)
            event.return_string(self._ok(self.set_last_page(file_id, page_index)))
        except (KeyError, ValueError, ManifestError) as exc:
            event.return_string(self._error("POSITION_SAVE_FAILED", str(exc)))

    def set_file_note_callback(self, event: Any) -> None:
        try:
            file_id = event.get_string_at(0)
            note = event.get_string_at(1)
            event.return_string(self._ok(self.set_file_note(file_id, note)))
        except (KeyError, ValueError, ManifestError) as exc:
            event.return_string(self._error("NOTE_SAVE_FAILED", str(exc)))

    def set_ui_options_callback(self, event: Any) -> None:
        try:
            options = json.loads(event.get_string())
            event.return_string(self._ok(self.set_ui_options(options)))
        except (json.JSONDecodeError, ValueError, ManifestError) as exc:
            event.return_string(self._error("UI_OPTIONS_SAVE_FAILED", str(exc)))

    def export_csv_callback(self, event: Any) -> None:
        try:
            event.return_string(self._ok({"csv": self.export_csv()}))
        except (ValueError, ManifestError) as exc:
            event.return_string(self._error("CSV_EXPORT_FAILED", str(exc)))

    def add_issue_callback(self, event: Any) -> None:
        try:
            event.return_string(self._ok(self.add_issue(event.get_string_at(0), json.loads(event.get_string_at(1)))))
        except (KeyError, ValueError, ManifestError, PdfDocumentError, OSError) as exc:
            event.return_string(self._error("ISSUE_SAVE_FAILED", str(exc)))

    def update_issue_callback(self, event: Any) -> None:
        try:
            event.return_string(self._ok(self.update_issue(
                event.get_string_at(0), event.get_string_at(1), json.loads(event.get_string_at(2)))))
        except (KeyError, ValueError, ManifestError, PdfDocumentError, OSError) as exc:
            event.return_string(self._error("ISSUE_SAVE_FAILED", str(exc)))

    def open_folder(self, folder: Path) -> dict[str, Any]:
        with self._lock:
            resolved = folder.expanduser().resolve()
            scanned = scan_pdf_folder(resolved)
            revision = manifest_revision(resolved)
            manifest = load_manifest(resolved)
            if manifest_revision(resolved) != revision:
                raise ManifestError("Manifest se během načítání změnil. Zkuste Načíst opravy znovu.")
            for pdf in scanned:
                ensure_file_entry(manifest, pdf)

            self.close()
            self.current_folder = resolved
            self.files = {item.file_id: item for item in scanned}
            self.manifest = manifest
            self._manifest_revision = revision
            self.active_file_id = None
            self.startup_error = None
            self.persistence_error = None
            return self.public_state()

    def open_document(self, file_id: str) -> dict[str, Any]:
        with self._lock:
            pdf = self._require_file(file_id)
            stat = pdf.path.stat()
            identity = FileIdentity(stat.st_size, stat.st_mtime_ns)
            if self.active_file_id != file_id or identity != pdf.identity or self.active_document is None:
                self.close()
                self.active_file_id = None
                self._document_sha256 = file_sha256(pdf.path)
                self.active_document = PdfDocument(pdf.path)
                after = pdf.path.stat()
                if (after.st_size, after.st_mtime_ns) != (identity.size, identity.mtime_ns):
                    self.close()
                    raise PdfDocumentError("PDF se během načítání změnilo. Načtěte opravy znovu.")
                pdf = ScannedPdf(file_id, pdf.name, pdf.path, identity)
                self.files[file_id] = pdf
                self.active_file_id = file_id
            assert self.active_document is not None
            entry = self._entry(file_id)
            assert self.manifest is not None
            previous_last_file = self.manifest["ui"].get("last_file")
            self.manifest["ui"]["last_file"] = file_id
            entry["ocr_sha256"] = self._document_sha256
            entry["resources"] = {**entry.get("resources", {}), **companion_resources(pdf.path)}
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest["ui"]["last_file"] = previous_last_file
                self._set_persistence_error(exc)
            return {
                "file_id": file_id,
                "name": pdf.name,
                "page_count": self.active_document.page_count,
                "pages": [item.to_dict() for item in self.active_document.page_metadata()],
                "status": entry.get("status", "unreviewed"),
                "last_page": entry.get("last_page", 0),
                "problem_pages": entry.get("problem_pages", []),
                "note": entry.get("note", ""),
                "persistence_error": self.persistence_error,
                **self._issue_state(file_id),
            }

    def _issue_state(self, file_id: str) -> dict[str, Any]:
        entry = self._entry(file_id)
        issues = copy.deepcopy(entry["issues"])
        for issue in issues:
            issue["stale"] = issue["target_sha256"] != self._document_sha256
        return {"issues": issues, "issue_counts": issue_counts(issues), "ocr_sha256": self._document_sha256}

    def _check_issue_document(self, file_id: str, expected_sha256: str) -> None:
        pdf = self._require_file(file_id)
        if self.active_file_id != file_id or self.active_document is None:
            raise ValueError("Dokument už není otevřený. Načtěte jej znovu.")
        if expected_sha256 != self._document_sha256 or file_sha256(pdf.path) != self._document_sha256:
            raise ValueError("PDF se změnilo. Nejdříve použijte Načíst opravy.")

    def _commit_issue(self, snapshot: dict[str, Any]) -> None:
        try:
            self._save_manifest()
        except ManifestError as exc:
            self.manifest = snapshot
            self._set_persistence_error(exc)
            raise

    def add_issue(self, file_id: str, data: Any) -> dict[str, Any]:
        with self._lock:
            if not isinstance(data, dict) or not isinstance(data.get("kind"), str) or data["kind"] not in ISSUE_KINDS:
                raise ValueError("Invalid issue kind.")
            self._check_issue_document(file_id, data.get("expected_sha256"))
            assert self.active_document is not None
            region = self.active_document.region_snapshot(data.get("page_index"), data.get("bbox"))
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            issue = {
                "id": str(uuid.uuid4()), **region, "kind": data["kind"],
                "note": data.get("note", ""), "status": "open",
                "source_sha256": self._document_sha256, "target_sha256": self._document_sha256,
                "created_at": now, "updated_at": now,
                "history": [{"at": now, "action": "created", "to": "open"}],
            }
            validate_issue(issue)
            snapshot = copy.deepcopy(self._require_manifest())
            entry = self._entry(file_id)
            entry["issues"].append(issue)
            self._commit_issue(snapshot)
            return {"file_id": file_id, "issue_id": issue["id"], **self._issue_state(file_id)}

    def update_issue(self, file_id: str, issue_id: str, patch: Any) -> dict[str, Any]:
        with self._lock:
            if not isinstance(patch, dict) or set(patch) - {"status", "kind", "note", "expected_sha256"}:
                raise ValueError("Invalid issue update.")
            self._check_issue_document(file_id, patch.get("expected_sha256"))
            entry = self._entry(file_id)
            index = next((i for i, issue in enumerate(entry["issues"]) if issue["id"] == issue_id), None)
            if index is None:
                raise ValueError("Připomínka neexistuje.")
            previous = entry["issues"][index]
            issue = copy.deepcopy(previous)
            status = patch.get("status", issue["status"])
            if not isinstance(status, str):
                raise ValueError("Invalid issue status.")
            if status not in {"open", "verified", "dismissed"} and status != issue["status"]:
                raise ValueError("Status fixed může zapsat pouze opravný postup s výsledkem opravy.")
            if status == "verified" and issue["status"] not in {"fixed", "verified"}:
                raise ValueError("Potvrdit lze pouze opravenou připomínku.")
            if status == "verified" and issue["target_sha256"] != self._document_sha256:
                raise ValueError("Připomínka patří k jiné verzi PDF. Nelze ji potvrdit.")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            changes = {key: value for key, value in patch.items() if key != "expected_sha256" and value != issue.get(key)}
            if not changes:
                return {"file_id": file_id, "issue_id": issue_id, **self._issue_state(file_id)}
            issue.update(changes)
            issue["updated_at"] = now
            issue["history"].append({
                "at": now, "action": "status_changed" if "status" in changes else "edited",
                "from": previous["status"], "to": status,
                "previous": {key: previous.get(key) for key in changes}, "changes": changes,
            })
            validate_issue(issue)
            snapshot = copy.deepcopy(self._require_manifest())
            entry["issues"][index] = issue
            self._commit_issue(snapshot)
            return {"file_id": file_id, "issue_id": issue_id, **self._issue_state(file_id)}

    def render_page_packet(
        self,
        request_id: str,
        file_id: str,
        page_index: int,
        target_width: int,
    ) -> bytes:
        with self._lock:
            if self.active_document is not None and self.active_file_id != file_id:
                raise PdfDocumentError("Obsolete page request for a document that is no longer active.")
            if self.active_document is None:
                self.open_document(file_id)
            assert self.active_document is not None
            rendered = self.active_document.render_page(page_index, target_width)
            header = {
                "request_id": request_id,
                "file_id": file_id,
                "page_index": rendered.page_index,
                "pixel_width": rendered.pixel_width,
                "pixel_height": rendered.pixel_height,
                "mime": rendered.mime_type,
                "ocr": rendered.ocr,
            }
            return pack_raw_packet(header, rendered.image_bytes)

    def set_file_status(self, file_id: str, status: str) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._require_manifest())
            if status not in VALID_FILE_STATUSES:
                raise ValueError(f"Unsupported status: {status}")
            entry = self._entry(file_id)
            entry["status"] = status
            entry["identity"] = self._require_file(file_id).identity.to_dict()
            entry["reviewed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return {"file_id": file_id, "status": status}

    def toggle_problem_page(self, file_id: str, page_index: int) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._require_manifest())
            if page_index < 0:
                raise ValueError("Page index cannot be negative.")
            entry = self._entry(file_id)
            pages = set(entry.get("problem_pages", []))
            if page_index in pages:
                pages.remove(page_index)
                selected = False
            else:
                pages.add(page_index)
                selected = True
            entry["problem_pages"] = sorted(pages)
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return {
                "file_id": file_id,
                "page_index": page_index,
                "selected": selected,
                "problem_pages": entry["problem_pages"],
            }

    def set_last_page(self, file_id: str, page_index: int) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._require_manifest())
            if page_index < 0:
                raise ValueError("Page index cannot be negative.")
            entry = self._entry(file_id)
            entry["last_page"] = page_index
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return {"file_id": file_id, "last_page": page_index}

    def set_file_note(self, file_id: str, note: str) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._require_manifest())
            entry = self._entry(file_id)
            entry["note"] = note
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return {"file_id": file_id, "note": note}

    def set_ui_options(self, options: Any) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._require_manifest())
            if not isinstance(options, dict):
                raise ValueError("UI options must be an object.")
            manifest = self._require_manifest()
            ui = manifest["ui"]
            if "issue_kind" in options:
                if not isinstance(options["issue_kind"], str) or options["issue_kind"] not in ISSUE_KINDS:
                    raise ValueError("Invalid issue kind.")
                ui["issue_kind"] = options["issue_kind"]
            if "zoom_percent" in options:
                zoom = int(options["zoom_percent"])
                if not 25 <= zoom <= 400:
                    raise ValueError("Zoom must be from 25 to 400 percent.")
                ui["zoom_percent"] = zoom
            if "ocr_mode" in options:
                mode = str(options["ocr_mode"])
                if mode not in VALID_OCR_MODES:
                    raise ValueError(f"Unsupported OCR mode: {mode}")
                ui["ocr_mode"] = mode
            if "overlay" in options:
                ui["overlay"] = bool(options["overlay"])
            if "status_filter" in options:
                status_filter = str(options["status_filter"])
                if status_filter != "all" and status_filter not in VALID_FILE_STATUSES:
                    raise ValueError(f"Unsupported status filter: {status_filter}")
                ui["status_filter"] = status_filter
            if "name_filter" in options:
                ui["name_filter"] = str(options["name_filter"])
            if "auto_advance" in options:
                ui["auto_advance"] = bool(options["auto_advance"])
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return dict(ui)

    def export_csv(self) -> str:
        with self._lock:
            manifest = self._require_manifest()
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow([
                "file", "status", "changed_since_review", "problem_pages",
                "note", "reviewed_at", "size", "mtime_ns",
            ])
            entries = manifest.get("files", {})
            for pdf in self.files.values():
                entry = entries.get(pdf.file_id, {})
                stored_identity = entry.get("identity") if isinstance(entry, dict) else None
                changed = bool(stored_identity and stored_identity != pdf.identity.to_dict())
                problem_pages = entry.get("problem_pages", []) if isinstance(entry, dict) else []
                writer.writerow([
                    pdf.name,
                    entry.get("status", "unreviewed"),
                    "true" if changed else "false",
                    ";".join(str(index + 1) for index in problem_pages),
                    entry.get("note", ""),
                    entry.get("reviewed_at") or "",
                    pdf.identity.size,
                    pdf.identity.mtime_ns,
                ])
            return output.getvalue()

    def public_state(self) -> dict[str, Any]:
        with self._lock:
            return self._public_state_unlocked()

    def _public_state_unlocked(self) -> dict[str, Any]:
        manifest = self.manifest or {
            "ui": {
                "last_file": None,
                "zoom_percent": 100,
                "ocr_mode": "layout",
                "overlay": False,
                "status_filter": "all",
                "name_filter": "",
                "auto_advance": True,
            },
            "files": {},
        }
        entries = manifest.get("files", {})
        return {
            "folder": str(self.current_folder) if self.current_folder else None,
            "files": [
                pdf.to_public_dict(entries.get(pdf.file_id))
                for pdf in self.files.values()
            ],
            "ui": dict(manifest.get("ui", {})),
            "startup_error": self.startup_error,
            "persistence_error": self.persistence_error,
        }

    def _entry(self, file_id: str) -> dict[str, Any]:
        pdf = self._require_file(file_id)
        manifest = self._require_manifest()
        return ensure_file_entry(manifest, pdf)

    def _require_file(self, file_id: str) -> ScannedPdf:
        try:
            return self.files[file_id]
        except KeyError as exc:
            raise KeyError(f"Unknown PDF file: {file_id}") from exc

    def _require_manifest(self) -> dict[str, Any]:
        if self.manifest is None or self.current_folder is None:
            raise ValueError("No folder is open.")
        return self.manifest

    def _save_manifest(self) -> None:
        manifest = self._require_manifest()
        assert self.current_folder is not None
        if manifest_revision(self.current_folder) != self._manifest_revision:
            raise ManifestError("Manifest změnil jiný nástroj. Použijte Načíst opravy; novější data nebyla přepsána.")
        self._manifest_revision = save_manifest(self.current_folder, manifest)
        self.persistence_error = None

    def _set_persistence_error(self, exc: Exception) -> None:
        self.persistence_error = {
            "code": "MANIFEST_WRITE_FAILED",
            "message": str(exc),
        }

    @staticmethod
    def _ok(data: Any) -> str:
        return json.dumps({"ok": True, "data": data, "error": None}, ensure_ascii=False)

    @staticmethod
    def _error(code: str, message: str) -> str:
        return json.dumps(
            {
                "ok": False,
                "data": None,
                "error": {"code": code, "message": message},
            },
            ensure_ascii=False,
        )

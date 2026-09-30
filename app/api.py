from __future__ import annotations

import copy
import csv
import io
import json
import threading
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .drafts import DraftStore
from .folder_dialog import FolderDialogError, select_folder
from .folder_scanner import FolderScanError, scan_pdf_folder
from .manifest import (
    ManifestError,
    ensure_file_entry,
    load_manifest,
    manifest_revision,
    save_manifest,
    validate_manifest,
    list_backups,
    restore_backup,
)
from .models import VALID_FILE_STATUSES, VALID_OCR_MODES, FileIdentity, ScannedPdf
from .pdf_document import PdfDocument, PdfDocumentError
from .raw_packet import pack_raw_packet
from .review import ISSUE_KINDS, companion_resources, file_sha256, issue_counts, validate_issue


class BackendApi:
    def __init__(self, initial_folder: Path | None = None):
        self._lock = threading.RLock()
        self.drafts = DraftStore()
        self.current_folder: Path | None = None
        self.files: dict[str, ScannedPdf] = {}
        self.manifest: dict[str, Any] | None = None
        self.active_file_id: str | None = None
        self.active_document: PdfDocument | None = None
        self.startup_error: dict[str, str] | None = None
        self.persistence_error: dict[str, str] | None = None
        self._manifest_revision: str | None = None
        self._document_sha256: str | None = None
        self.context_id = str(uuid.uuid4())
        self.document_id: str | None = None
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
            self.document_id = None

    def bind(self, window: Any) -> None:
        bindings = {
            "selectFolderB": (0, self.select_folder_callback), "openFolderB": (1, self.open_folder_callback),
            "refreshFolderB": (0, self.refresh_folder_callback), "openDocumentB": (1, self.open_document_callback),
            "requestPageB": (4, self.request_page_callback), "setFileStatusB": (2, self.set_file_status_callback),
            "setReviewCompleteB": (2, self.set_review_complete_callback),
            "toggleProblemPageB": (2, self.toggle_problem_page_callback), "setLastPageB": (2, self.set_last_page_callback),
            "setFileNoteB": (2, self.set_file_note_callback), "setUiOptionsB": (1, self.set_ui_options_callback),
            "exportCsvB": (0, self.export_csv_callback), "addIssueB": (2, self.add_issue_callback),
            "updateIssueB": (3, self.update_issue_callback),
        }
        window.bind("syncStateB", self.sync_state_callback)
        window.bind("saveDraftB", self.save_draft_callback)
        window.bind("deleteDraftB", self.delete_draft_callback)
        window.bind("listBackupsB", self.list_backups_callback)
        window.bind("restoreBackupB", self.restore_backup_callback)
        document_bound = {"requestPageB", "setFileStatusB", "toggleProblemPageB", "setLastPageB", "setFileNoteB", "addIssueB", "updateIssueB"}
        for name, (argc, callback) in bindings.items():
            window.bind(name, self._context_callback(callback, argc, name in document_bound, 1 if name == "requestPageB" else 0))

    def _context_callback(self, callback, argc: int, document_bound: bool, file_argument: int = 0):
        def guarded(event):
            with self._lock:
                try:
                    context = json.loads(event.get_string_at(argc))
                    if not isinstance(context, dict) or context.get("context_id") != self.context_id:
                        raise ValueError("Složka už není aktuální. Načtěte její stav znovu.")
                    if document_bound and (context.get("document_id") != self.document_id or self.active_file_id is None
                                           or event.get_string_at(file_argument) != self.active_file_id):
                        raise ValueError("Dokument už není aktuální. Operace nebyla provedena.")
                except (ValueError, TypeError, IndexError):
                    event.return_string(self._error("STALE_CONTEXT", "Kontext požadavku se změnil; operace nebyla provedena."))
                    return
                callback(event)
        return guarded

    def save_draft_callback(self, event):
        try:
            self.drafts.put(json.loads(event.get_string_at(0)))
            event.return_string(self._ok({}))
        except (ValueError, OSError, sqlite3.Error) as exc:
            event.return_string(self._error("DRAFT_SAVE_FAILED", f"Koncept se nepodařilo uložit lokálně: {exc}"))

    def delete_draft_callback(self, event):
        try:
            self.drafts.remove(event.get_string_at(0))
            event.return_string(self._ok({}))
        except (ValueError, OSError, sqlite3.Error) as exc:
            event.return_string(self._error("DRAFT_SAVE_FAILED", str(exc)))

    def list_backups_callback(self, event):
        try:
            folder = Path(event.get_string_at(0)).expanduser().resolve()
            event.return_string(self._ok({"folder": str(folder), "revision": manifest_revision(folder), "backups": list_backups(folder)}))
        except (OSError, ValueError, ManifestError) as exc:
            event.return_string(self._error("BACKUP_LIST_FAILED", str(exc)))

    def restore_backup_callback(self, event):
        try:
            folder = Path(event.get_string_at(0)).expanduser().resolve()
            revision = json.loads(event.get_string_at(2))
            with self._lock:
                restore_backup(folder, event.get_string_at(1), expected_revision=revision)
                event.return_string(self._ok(self.open_folder(folder)))
        except (OSError, ValueError, ManifestError, FolderScanError) as exc:
            event.return_string(self._error("BACKUP_RESTORE_FAILED", str(exc)))

    def _draft_state(self):
        try:
            return {"drafts": self.drafts.list(self.current_folder) if self.current_folder else [], "draft_error": None}
        except (OSError, ValueError, sqlite3.Error) as exc:
            return {"drafts": [], "draft_error": f"Obnovené poznámky nelze načíst: {exc}"}

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

    def set_review_complete_callback(self, event: Any) -> None:
        try:
            result = self.set_review_complete(event.get_string_at(0), json.loads(event.get_string_at(1)))
            event.return_string(self._ok(result))
        except (KeyError, ValueError, ManifestError, OSError) as exc:
            event.return_string(self._error("REVIEW_SAVE_FAILED", str(exc)))

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
                raise ManifestError("Manifest se během načítání změnil. Zkuste Obnovit znovu.")
            for pdf in scanned:
                ensure_file_entry(manifest, pdf)

            self.close()
            self.current_folder = resolved
            self.files = {item.file_id: item for item in scanned}
            self.manifest = manifest
            self._manifest_revision = revision
            self.active_file_id = None
            self.context_id = str(uuid.uuid4())
            self.startup_error = None
            self.persistence_error = None
            return self.public_state()

    def open_document(self, file_id: str) -> dict[str, Any]:
        with self._lock:
            pdf = self._require_file(file_id)
            stat = pdf.path.stat()
            identity = FileIdentity(stat.st_size, stat.st_mtime_ns)
            if self.active_file_id != file_id or identity != pdf.identity or self.active_document is None:
                candidate_hash = file_sha256(pdf.path)
                candidate = PdfDocument(pdf.path)
                try:
                    pages = candidate.page_metadata()
                    after = pdf.path.stat()
                    if (after.st_size, after.st_mtime_ns) != (identity.size, identity.mtime_ns):
                        raise PdfDocumentError("PDF se během načítání změnilo. Použijte Obnovit.")
                except Exception:
                    candidate.close()
                    raise
                self.close()
                self.active_document = candidate
                self._document_sha256 = candidate_hash
                pdf = ScannedPdf(file_id, pdf.name, pdf.path, identity)
                self.files[file_id] = pdf
                self.active_file_id = file_id
                self.document_id = str(uuid.uuid4())
            else:
                pages = self.active_document.page_metadata()
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
                "pages": [item.to_dict() for item in pages],
                "document_id": self.document_id,
                "manifest_revision": self._manifest_revision,
                "status": entry.get("status", "unreviewed"),
                "review_complete": entry["review_complete"],
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
            issue["invalid_target"] = self._invalid_issue_target(issue)
        return {"issues": issues, "issue_counts": issue_counts(issues), "ocr_sha256": self._document_sha256}

    def _invalid_issue_target(self, issue: dict[str, Any]) -> bool:
        if self.active_document is None or issue["page_index"] >= self.active_document.page_count:
            return True
        page = self.active_document.page_geometry(issue["page_index"])
        return any(abs(issue[key] - page[key]) > 0.01 for key in ("page_width", "page_height", "page_rotation"))

    def _check_issue_document(self, file_id: str, expected_sha256: str) -> None:
        pdf = self._require_file(file_id)
        if self.active_file_id != file_id or self.active_document is None:
            raise ValueError("Dokument už není otevřený. Načtěte jej znovu.")
        if expected_sha256 != self._document_sha256 or file_sha256(pdf.path) != self._document_sha256:
            raise ValueError("PDF se změnilo. Nejdříve použijte Obnovit.")

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
            if status == "verified" and self._invalid_issue_target(issue):
                raise ValueError("Připomínka neodpovídá stránce aktuálního PDF. Nelze ji potvrdit.")
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

    def set_review_complete(self, file_id: str, payload: Any) -> dict[str, Any]:
        with self._lock:
            if (not isinstance(payload, dict) or type(payload.get("complete")) is not bool
                    or set(payload) not in ({"complete", "expected_sha256"},
                                           {"complete", "expected_identity"},
                                           {"complete", "expected_identity", "expected_sha256"})):
                raise ValueError("Invalid review completion update.")
            pdf = self._require_file(file_id)
            if "expected_identity" in payload:
                stat = pdf.path.stat()
                actual = FileIdentity(stat.st_size, stat.st_mtime_ns).to_token()
                if payload["expected_identity"] != pdf.identity.to_token() or actual != payload["expected_identity"]:
                    raise ValueError("PDF se změnilo. Nejdříve použijte Obnovit.")
            if "expected_sha256" in payload and payload["expected_sha256"] != file_sha256(pdf.path):
                raise ValueError("PDF se změnilo. Nejdříve použijte Obnovit.")
            snapshot = copy.deepcopy(self._require_manifest())
            entry = self._entry(file_id)
            entry["review_complete"] = payload["complete"]
            entry["review_completed_at"] = (datetime.now().astimezone().isoformat(timespec="seconds")
                                             if payload["complete"] else None)
            entry["identity"] = self._require_file(file_id).identity.to_dict()
            try:
                self._save_manifest()
            except ManifestError as exc:
                self.manifest = snapshot
                self._set_persistence_error(exc)
                raise
            return self._require_file(file_id).to_public_dict(entry)

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
            known = {"issue_kind", "zoom_percent", "ocr_mode", "overlay", "status_filter", "name_filter", "auto_advance", "issue_filter", "review_filter"}
            if set(options) - known:
                raise ValueError("Unknown UI option.")
            candidate = copy.deepcopy(manifest)
            candidate["ui"].update(options)
            validate_manifest(candidate)
            self.manifest = candidate
            ui = candidate["ui"]
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
                "note", "reviewed_at", "size", "mtime_ns", "review_complete", "review_completed_at",
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
                    "true" if entry.get("review_complete", entry.get("status") == "ok") else "false",
                    entry.get("review_completed_at") or "",
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
            "context_id": self.context_id,
            **self._draft_state(),
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
        self._manifest_revision = save_manifest(self.current_folder, manifest, expected_revision=self._manifest_revision)
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

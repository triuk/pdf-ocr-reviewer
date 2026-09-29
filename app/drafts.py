"""Durable, local note drafts independent of the shared review manifest."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from pathlib import Path


def state_directory() -> Path:
    override = os.environ.get("PDF_OCR_REVIEWER_STATE_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local" / "state") / "pdf-ocr-reviewer"


class DraftStore:
    def __init__(self, folder: Path | None = None):
        self.path = (folder or state_directory()) / "drafts.sqlite3"

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=3)
        try:
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS drafts (key TEXT PRIMARY KEY, folder TEXT NOT NULL, token TEXT NOT NULL, payload TEXT NOT NULL)")
                yield connection
        finally:
            connection.close()

    def put(self, draft: dict) -> None:
        required = ("folder", "fileId", "token", "note", "base_note", "expected_sha256")
        if not isinstance(draft, dict) or any(not isinstance(draft.get(k), str) for k in required):
            raise ValueError("Invalid note draft.")
        if draft.get("issueId") is not None and not isinstance(draft["issueId"], str):
            raise ValueError("Invalid draft issue ID.")
        folder = str(Path(draft["folder"]).resolve())
        key = json.dumps([folder, draft["fileId"], draft.get("issueId")], ensure_ascii=False)
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO drafts VALUES (?, ?, ?, ?)",
                               (key, folder, draft["token"], json.dumps(draft, ensure_ascii=False)))

    def remove(self, token: str) -> None:
        if not isinstance(token, str):
            raise ValueError("Invalid draft token.")
        if not self.path.exists():
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM drafts WHERE token = ?", (token,))

    def list(self, folder: Path) -> list[dict]:
        if not self.path.exists():
            return []
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM drafts WHERE folder = ? ORDER BY rowid", (str(folder.resolve()),))
            return [json.loads(row[0]) for row in rows]

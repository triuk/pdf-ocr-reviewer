from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.manifest import (
    MANIFEST_FILENAME,
    ManifestFormatError,
    default_manifest,
    load_manifest,
    save_manifest,
)


def test_missing_manifest_returns_defaults(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path)
    assert manifest["schema_version"] == 1
    assert manifest["files"] == {}
    assert manifest["ui"]["ocr_mode"] == "pdf_order"
    assert manifest["ui"]["overlay"] is True


def test_manifest_round_trip_preserves_unknown_fields(tmp_path: Path) -> None:
    manifest = default_manifest()
    manifest["future_field"] = {"keep": True}
    manifest["files"]["a.pdf"] = {
        "identity": {"size": 10, "mtime_ns": 20},
        "status": "ok",
        "last_page": 1,
        "problem_pages": [1],
        "note": "test",
        "reviewed_at": None,
        "future_entry": 123,
    }

    save_manifest(tmp_path, manifest)
    loaded = load_manifest(tmp_path)

    assert loaded["future_field"] == {"keep": True}
    assert loaded["files"]["a.pdf"]["future_entry"] == 123
    assert loaded["updated_at"] is not None


def test_invalid_json_is_not_silently_reset(tmp_path: Path) -> None:
    (tmp_path / MANIFEST_FILENAME).write_text("{broken", encoding="utf-8")
    with pytest.raises(ManifestFormatError):
        load_manifest(tmp_path)


def test_invalid_status_is_rejected(tmp_path: Path) -> None:
    manifest = default_manifest()
    manifest["files"]["a.pdf"] = {"status": "made_up", "problem_pages": []}
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestFormatError):
        load_manifest(tmp_path)

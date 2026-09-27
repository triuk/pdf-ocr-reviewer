from __future__ import annotations

import copy
import json
from pathlib import Path

import pymupdf
import pytest

from app.api import BackendApi
from app.manifest import MANIFEST_FILENAME, ManifestError, ManifestFormatError, ManifestWriteError, load_manifest, save_manifest
from app.pdf_document import PdfDocument, PdfDocumentError
from app.review import file_sha256


@pytest.fixture
def reviewed(tmp_path):
    path = tmp_path / "sample-ocr.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 50), "First OCR line", fontsize=12)
        doc.save(path)
    for suffix in ("qa2.md", "qa3.md"):
        (tmp_path / f"sample-{suffix}").write_text("status: PASS\n", encoding="utf-8")
    api = BackendApi(tmp_path)
    opened = api.open_document(path.name)
    with PdfDocument(path) as doc:
        word = doc.render_page(0, 600).ocr["layout_items"][0]
    payload = {"page_index": 0, "bbox": [word[k] for k in ("x0", "y0", "x1", "y1")],
               "kind": "oversized", "expected_sha256": opened["ocr_sha256"]}
    try:
        yield api, path, payload
    finally:
        api.close()


def simulate_repair(path: Path, issue_id: str) -> str:
    manifest = load_manifest(path.parent)
    issue = next(i for i in manifest["files"][path.name]["issues"] if i["id"] == issue_id)
    sha = file_sha256(path)
    issue["status"] = "fixed"
    issue["result"] = {"summary": "Geometry checked", "before_sha256": sha, "after_sha256": sha, "at": "2026-09-25T20:00:00+02:00"}
    issue["history"].append({"action": "fixed", "at": issue["result"]["at"], "from": "open", "to": "fixed"})
    save_manifest(path.parent, manifest)
    return sha


def test_annotation_round_trip_and_companions(reviewed):
    api, path, payload = reviewed
    before = path.read_bytes()
    response = api.add_issue(path.name, payload)
    issue = response["issues"][0]
    assert issue["text"] == "First"
    assert len(issue["targets"]) == 1
    assert issue["source_sha256"] == file_sha256(path)
    assert issue["target_sha256"] == issue["source_sha256"]
    assert issue["status"] == "open"
    assert not issue["stale"]
    assert response["issue_counts"]["open"] == 1
    api.update_issue(path.name, issue["id"], {"note": "Text je správně", "expected_sha256": payload["expected_sha256"]})
    api.open_folder(path.parent)
    doc = api.open_document(path.name)
    assert doc["issues"][0]["note"] == "Text je správně"
    saved = load_manifest(path.parent)
    assert saved["files"][path.name]["resources"] == {"qa2": "sample-qa2.md", "qa3": "sample-qa3.md"}
    assert path.read_bytes() == before


def test_confirm_reopen_preserve_repair_history_and_pdf(reviewed):
    api, path, payload = reviewed
    issue_id = api.add_issue(path.name, payload)["issue_id"]
    sha = simulate_repair(path, issue_id)
    api.open_folder(path.parent)
    assert api.open_document(path.name)["issues"][0]["status"] == "fixed"
    for status in ("verified", "open", "dismissed", "open"):
        data = api.update_issue(path.name, issue_id, {"status": status, "expected_sha256": sha})
        assert data["issues"][0]["status"] == status
    issue = data["issues"][0]
    assert len(issue["history"]) == 6
    assert issue["result"]["summary"] == "Geometry checked"
    assert file_sha256(path) == sha
    assert api.public_state()["files"][0]["issue_counts"]["open"] == 1


def test_external_manifest_cannot_be_overwritten_by_any_save(reviewed):
    api, path, payload = reviewed
    issue_id = api.add_issue(path.name, payload)["issue_id"]
    simulate_repair(path, issue_id)
    current = (path.parent / MANIFEST_FILENAME).read_bytes()
    with pytest.raises(ManifestError, match="jiný nástroj"):
        api.set_last_page(path.name, 0)
    with pytest.raises(ManifestError):
        api.add_issue(path.name, payload)
    assert (path.parent / MANIFEST_FILENAME).read_bytes() == current
    assert len(api.manifest["files"][path.name]["issues"]) == 1
    api.open_folder(path.parent)
    assert api.open_document(path.name)["issues"][0]["status"] == "fixed"


def test_write_failure_rolls_back_issue(reviewed, monkeypatch):
    api, path, payload = reviewed
    original = copy.deepcopy(api.manifest)
    def fail(*args):
        raise ManifestWriteError("read only")
    monkeypatch.setattr("app.api.save_manifest", fail)
    with pytest.raises(ManifestWriteError):
        api.add_issue(path.name, payload)
    assert api.manifest == original


def test_external_write_immediately_after_save_is_not_adopted_as_our_revision(reviewed, monkeypatch):
    api, path, payload = reviewed
    real_save = save_manifest
    def save_then_external_edit(folder, manifest):
        written_hash = real_save(folder, manifest)
        external = load_manifest(folder)
        external["external_change"] = "must survive"
        real_save(folder, external)
        return written_hash
    monkeypatch.setattr("app.api.save_manifest", save_then_external_edit)
    api.set_file_note(path.name, "our note")
    with pytest.raises(ManifestError):
        api.add_issue(path.name, payload)
    assert load_manifest(path.parent)["external_change"] == "must survive"


def test_stale_page_request_does_not_switch_active_review_document(reviewed):
    api, path, payload = reviewed
    second = path.parent / "second.pdf"
    second.write_bytes(path.read_bytes())
    api.open_folder(path.parent)
    api.open_document(path.name)
    api.open_document(second.name)
    with pytest.raises(PdfDocumentError, match="Obsolete"):
        api.render_page_packet("late", path.name, 0, 600)
    assert api.active_file_id == second.name
    assert api.add_issue(second.name, payload)["issues"][0]["status"] == "open"


@pytest.mark.parametrize("patch", [
    {"bbox": [0, 0, 0, 1]}, {"bbox": [-1, 0, 5, 5]}, {"bbox": [0, 0, 301, 5]},
    {"bbox": [0, 0, float("nan"), 1]}, {"bbox": "wrong"},
    {"page_index": 1}, {"page_index": -1}, {"page_index": True},
    {"kind": "unknown"}, {"note": 99}, {"expected_sha256": "0" * 64},
])
def test_bad_region_requests_do_not_mutate_manifest(reviewed, patch):
    api, path, payload = reviewed
    original = copy.deepcopy(api.manifest)
    with pytest.raises(ValueError):
        api.add_issue(path.name, {**payload, **patch})
    assert api.manifest == original


def test_stale_pdf_detection_and_blocked_confirmation(reviewed):
    api, path, payload = reviewed
    issue_id = api.add_issue(path.name, payload)["issue_id"]
    simulate_repair(path, issue_id)
    with pymupdf.open(path) as doc:
        doc.set_metadata({"title": "new revision"})
        doc.saveIncr()
    with pytest.raises(ValueError, match="PDF se změnilo"):
        api.add_issue(path.name, payload)
    api.open_folder(path.parent)
    opened = api.open_document(path.name)
    assert opened["issues"][0]["stale"]
    with pytest.raises(ValueError, match="jiné verzi"):
        api.update_issue(path.name, issue_id, {"status": "verified", "expected_sha256": opened["ocr_sha256"]})


def test_cannot_confirm_open_or_claim_fixed_without_repair(reviewed):
    api, path, payload = reviewed
    issue_id = api.add_issue(path.name, payload)["issue_id"]
    for status in ("verified", "fixed", "unknown"):
        with pytest.raises(ValueError):
            api.update_issue(path.name, issue_id, {"status": status, "expected_sha256": payload["expected_sha256"]})


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_display_coordinates_on_cropped_rotated_page(tmp_path, rotation):
    path = tmp_path / "rotated.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=700)
        page.insert_text((150, 200), "Target", fontsize=18)
        page.set_cropbox(pymupdf.Rect(100, 100, 450, 650))
        page.set_rotation(rotation)
        doc.save(path)
    with pymupdf.open(path) as doc:
        page = doc[0]
        expected = pymupdf.Rect(page.get_text("words")[0][:4]) * page.rotation_matrix
    with PdfDocument(path) as doc:
        rendered = doc.render_page(0, 700)
        word = rendered.ocr["layout_items"][0]
        bbox = [word[k] for k in ("x0", "y0", "x1", "y1")]
        assert bbox == pytest.approx(tuple(expected))
        region = doc.region_snapshot(0, bbox)
        assert region["text"] == "Target"
        assert region["page_rotation"] == rotation
        assert region["page_width"] == rendered.ocr["page_width"]


@pytest.mark.parametrize("mutation", ["duplicate", "status", "hash", "bbox", "result"])
def test_invalid_external_issue_data_is_rejected(reviewed, mutation):
    api, path, payload = reviewed
    api.add_issue(path.name, payload)
    manifest = load_manifest(path.parent)
    issues = manifest["files"][path.name]["issues"]
    if mutation == "duplicate": issues.append(copy.deepcopy(issues[0]))
    if mutation == "status": issues[0]["status"] = "fake"
    if mutation == "hash": issues[0]["target_sha256"] = "invalid"
    if mutation == "bbox": issues[0]["bbox"][2] = float("inf")
    if mutation == "result": issues[0]["status"] = "fixed"
    (path.parent / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestFormatError):
        load_manifest(path.parent)

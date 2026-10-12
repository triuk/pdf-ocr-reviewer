from __future__ import annotations

import copy
import json

import pymupdf
import pytest

from app.api import BackendApi
from app.manifest import load_manifest, manifest_revision, save_manifest, ManifestFormatError
from app.pdf_document import PdfDocument
from app.review import file_sha256


def marker_pdf(path, rotation=0, text="Gajdoš[NEČITELNÉ]ková [NEČITELNÉ],"):
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=700)
        page.insert_font(fontname="unicode", fontbuffer=pymupdf.Font("cjk").buffer)
        page.insert_text((120, 180), text, fontname="unicode")
        # Different font sizes split the marker into spans on the same line.
        page.insert_text((120, 240), "[NEČ", fontname="unicode", fontsize=11)
        x = 120 + pymupdf.Font("cjk").text_length("[NEČ", fontsize=11)
        page.insert_text((x, 240), "ITELNÉ]", fontname="unicode", fontsize=12)
        page.set_cropbox(pymupdf.Rect(100, 100, 450, 650))
        page.set_rotation(rotation)
        doc.save(path)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_subword_punctuation_spans_and_display_geometry(tmp_path, rotation):
    path = tmp_path / "markers.pdf"
    marker_pdf(path, rotation)
    with PdfDocument(path) as doc:
        regions = doc.unreadable_regions()
        assert len(regions) == 3
        assert regions[0]["context_before"] == "Gajdoš"
        assert regions[0]["context_after"].startswith("ková")
        assert regions[1]["context_after"] == ","
        for region in regions:
            assert region["page_rotation"] == rotation
            assert region["text"] == "[NEČITELNÉ]"
            assert doc.region_snapshot(0, region["bbox"])["targets"]
        # The embedded marker box excludes the readable prefix and suffix.
        word = regions[0]["targets"][0]
        axis = (0, 2, "x0", "x1") if rotation in (0, 180) else (1, 3, "y0", "y1")
        assert regions[0]["bbox"][axis[1]] - regions[0]["bbox"][axis[0]] < word[axis[3]] - word[axis[2]]


def test_import_edit_empty_reload_and_dismissal(tmp_path):
    path = tmp_path / "markers.pdf"
    marker_pdf(path)
    before = path.read_bytes()
    api = BackendApi(tmp_path)
    try:
        opened = api.open_document(path.name)
        assert opened["issue_counts"]["open"] == 3
        ids = [issue["id"] for issue in opened["issues"]]
        patch = {"expected_sha256": opened["ocr_sha256"]}
        api.update_issue(path.name, ids[0], {**patch, "replacement_text": "  í  ", "note": "Z papírového výtisku"})
        api.update_issue(path.name, ids[1], {**patch, "replacement_text": " \n "})
        api.update_issue(path.name, ids[2], {**patch, "status": "dismissed"})
        api.open_folder(tmp_path)
        reopened = api.open_document(path.name)
        assert [i["id"] for i in reopened["issues"]] == ids
        assert reopened["issues"][0]["replacement_text"] == "  í  "
        assert reopened["issues"][0]["note"] == "Z papírového výtisku"
        assert reopened["issues"][0]["status"] == "open"
        assert reopened["issues"][1]["replacement_text"] == " \n "
        assert reopened["issues"][1]["status"] == "open"
        assert reopened["issues"][2]["status"] == "dismissed"
        assert path.read_bytes() == before
        assert load_manifest(tmp_path)["repair_instructions"]["note_handling"]["placeholder"]
    finally:
        api.close()


@pytest.mark.parametrize("legacy", [False, True], ids=["new-manifest", "upgrade-v5"])
@pytest.mark.parametrize("original,supplied,effective,result", [
    ("Gajdoš[NEČITELNÉ]ková", "Gajdošíková", "í", "Gajdošíková"),
    ("Gajdoš[NEČITELNÉ]ková", "í", "í", "Gajdošíková"),
    ("[NEČITELNÉ].", "2.", "2", "2."),
    ("[NEČITELNÉ].", "2", "2", "2."),
])
def test_exported_overlap_contract_preserves_user_text_and_extensions(tmp_path, legacy, original, supplied, effective, result):
    """Reviewer exports the repair contract; the external worker performs it."""
    from app.manifest import MANIFEST_FILENAME
    from app.review import repair_instructions

    path = tmp_path / "markers.pdf"
    marker_pdf(path, text=original)
    before_hash = file_sha256(path)
    api = BackendApi(tmp_path)
    try:
        opened = api.open_document(path.name)
        issue = opened["issues"][0]
        api.update_issue(path.name, issue["id"], {"replacement_text": supplied, "note": "User note",
                         "expected_sha256": opened["ocr_sha256"]})
        candidate = load_manifest(tmp_path)
        candidate["custom"] = {"preserve": [1, 2]}
        entry = candidate["files"][path.name]
        entry["issues"][0]["custom"] = {"original": True}
        entry["note"] = "Shared user note"
        instructions = candidate["repair_instructions"]
        instructions["custom"] = "Preserve this extension"
        instructions["note_handling"]["custom"] = "Keep custom note policy"
        instructions["note_handling"]["issue_note"] = "Keep our issue note policy"
        instructions["rules"].append("Keep our extra rule")
        if legacy:
            instructions["version"] = 5
            instructions["note_handling"]["placeholder"] = "replacement_text je náhrada pouze samotné značky."
        expected_files = copy.deepcopy(candidate["files"])
        expected_instructions = copy.deepcopy(instructions)
        save_manifest(tmp_path, candidate, expected_revision=manifest_revision(tmp_path))
        api.open_folder(tmp_path)
        api.open_document(path.name)  # Normal reviewer update persists the migrated policy.
        exported = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        policy = exported["repair_instructions"]["note_handling"]["placeholder"]
        assert exported["repair_instructions"]["version"] == 6
        assert policy == repair_instructions()["note_handling"]["placeholder"]
        assert f"{original} | {supplied} | {effective} | {result}" in policy
        assert "kvůli jednoznačnému překryvu nevyžaduj další potvrzení" in policy
        assert "podle aktuálního PDF a ověřeného kontextu" in policy
        assert "by po odstranění překryvu byla prázdná, ponech místo open" in policy
        assert "v result.summary a historii" in policy
        assert exported["files"] == expected_files
        assert exported["custom"] == candidate["custom"]
        expected_instructions["version"] = 6
        expected_instructions["note_handling"]["placeholder"] = policy
        assert exported["repair_instructions"] == expected_instructions
        assert exported["files"][path.name]["issues"][0]["replacement_text"] == supplied
        assert file_sha256(path) == before_hash
    finally:
        api.close()


def test_changed_replacement_reopens_fixed_issue_and_preserves_result(tmp_path):
    path = tmp_path / "markers.pdf"
    marker_pdf(path)
    api = BackendApi(tmp_path)
    try:
        opened = api.open_document(path.name)
        manifest = load_manifest(tmp_path)
        issue = manifest["files"][path.name]["issues"][0]
        issue["status"] = "fixed"
        issue["replacement_text"] = "a"
        issue["result"] = {"summary": "Previous attempt", "at": "2026-10-11T12:00:00+02:00",
                           "before_sha256": opened["ocr_sha256"], "after_sha256": opened["ocr_sha256"]}
        result = copy.deepcopy(issue["result"])
        save_manifest(tmp_path, manifest, expected_revision=manifest_revision(tmp_path))
        api.open_folder(tmp_path)
        api.open_document(path.name)
        response = api.update_issue(path.name, issue["id"], {"replacement_text": "", "expected_sha256": file_sha256(path)})
        assert response["issues"][0]["status"] == "open"
        assert response["issues"][0]["result"] == result
    finally:
        api.close()


def test_invalid_replacement_and_stale_target_are_rejected(tmp_path):
    path = tmp_path / "markers.pdf"
    marker_pdf(path)
    api = BackendApi(tmp_path)
    try:
        opened = api.open_document(path.name)
        issue = opened["issues"][0]
        with pytest.raises(ValueError):
            api.update_issue(path.name, issue["id"], {"replacement_text": 42, "expected_sha256": opened["ocr_sha256"]})
        manifest = load_manifest(tmp_path)
        manifest["files"][path.name]["issues"][0]["target_sha256"] = "0" * 64
        save_manifest(tmp_path, manifest, expected_revision=manifest_revision(tmp_path))
        api.open_folder(tmp_path)
        api.open_document(path.name)
        with pytest.raises(ValueError):
            api.update_issue(path.name, issue["id"], {"replacement_text": "abc", "expected_sha256": opened["ocr_sha256"]})
        manifest["files"][path.name]["issues"][0]["replacement_text"] = []
        with pytest.raises(ManifestFormatError):
            save_manifest(tmp_path, manifest, expected_revision=manifest_revision(tmp_path))
    finally:
        api.close()

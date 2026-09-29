from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.manifest import manifest_revision

from app.manifest import (
    MANIFEST_FILENAME,
    ManifestFormatError,
    default_manifest,
    load_manifest,
    save_manifest,
)


def test_missing_manifest_returns_defaults(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path)
    assert manifest["schema_version"] == 2
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

    save_manifest(tmp_path, manifest, expected_revision=manifest_revision(tmp_path))
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


def test_v1_migration_preserves_all_review_data_and_unknown_fields(tmp_path: Path) -> None:
    original = default_manifest()
    original.pop("repair_instructions")
    original["schema_version"] = 1
    original["future"] = {"preserve": True}
    original["ui"]["last_file"] = "a.pdf"
    original["files"]["a.pdf"] = {"status": "error", "note": "Ruční poznámka", "problem_pages": [1], "future": 42}
    path = tmp_path / MANIFEST_FILENAME
    path.write_text(json.dumps(original), encoding="utf-8")
    migrated = load_manifest(tmp_path)
    assert migrated["schema_version"] == 2
    assert migrated["files"]["a.pdf"] == {**original["files"]["a.pdf"], "issues": []}
    assert migrated["ui"] == original["ui"]
    assert migrated["future"] == original["future"]
    assert json.loads(path.read_text())["schema_version"] == 1  # read-only until save
    save_manifest(tmp_path, migrated, expected_revision=manifest_revision(tmp_path))
    assert next(iter(json.loads(path.read_text()))) == "repair_instructions"
    assert load_manifest(tmp_path) == migrated


@pytest.mark.parametrize("version", [1, 2])
def test_old_repair_contract_migrates_without_requeueing_accepted_issues(tmp_path, version):
    import copy
    from app.manifest import migrate_manifest
    from app.review import repair_instructions
    data = default_manifest()
    legacy = json.loads((Path(__file__).parent / 'fixtures/repair-instructions-v2.json').read_text())
    legacy['version'] = version
    if version == 1:
        legacy.pop('writer_protocol')
        legacy['rules'][-1] = legacy['rules'][-1].replace('pomocí writer_protocol', 'atomicky')
    legacy['custom'] = {'preserve': True}
    legacy['rules'].append('My additional rule')
    legacy['statuses']['custom'] = 'Keep this too'
    data['repair_instructions'] = legacy
    data['files']['a.pdf'] = {'issues': [{'status': status, 'history': [{'custom': status}]}
                                       for status in ('open', 'fixed', 'verified', 'dismissed')]}
    original = copy.deepcopy(data)
    migrated = migrate_manifest(data)
    instructions = migrated['repair_instructions']
    assert instructions['version'] == 3
    assert instructions['rules'] == repair_instructions()['rules'] + ['My additional rule']
    assert instructions['workflow']['eligible_statuses'] == ['open', 'fixed']
    assert instructions['workflow']['excluded_statuses'] == ['dismissed', 'verified']
    assert instructions['custom'] == {'preserve': True}
    assert instructions['statuses']['custom'] == 'Keep this too'
    assert migrated['files'] == original['files']
    assert data == original
    assert migrate_manifest(migrated) == migrated


@pytest.mark.parametrize('status,complete', [('ok', True), ('unreviewed', False), ('error', False), ('needs_review', False)])
def test_legacy_file_completion_preserves_classification(tmp_path, status, complete):
    from app.manifest import ensure_file_entry
    from app.models import FileIdentity, ScannedPdf
    data = default_manifest()
    entry = {'status': status, 'reviewed_at': '2026-09-29T12:00:00+02:00', 'note': 'Keep'}
    data['files']['one.pdf'] = entry
    pdf = ScannedPdf('one.pdf', 'one.pdf', tmp_path / 'one.pdf', FileIdentity(10, 20))
    assert pdf.to_public_dict(entry)['review_complete'] is complete
    ensure_file_entry(data, pdf)
    assert entry['review_complete'] is complete
    assert entry['status'] == status
    assert entry['note'] == 'Keep'
    # Explicit unchecking overrides historical OK on every subsequent load.
    entry['review_complete'] = False
    ensure_file_entry(data, pdf)
    assert pdf.to_public_dict(entry)['review_complete'] is False

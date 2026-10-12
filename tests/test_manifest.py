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
    assert manifest["ui"]["issue_kind"] == "geometry"


@pytest.mark.parametrize("kind", ["position", "oversized"])
def test_removed_geometry_preferences_are_rejected(tmp_path, kind):
    manifest = default_manifest()
    manifest["ui"]["issue_kind"] = kind
    with pytest.raises(ManifestFormatError, match="ui.issue_kind"):
        save_manifest(tmp_path, manifest, expected_revision=None)


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
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1  # read-only until save
    save_manifest(tmp_path, migrated, expected_revision=manifest_revision(tmp_path))
    assert next(iter(json.loads(path.read_text(encoding="utf-8")))) == "repair_instructions"
    assert load_manifest(tmp_path) == migrated


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_repair_contract_migrates_without_requeueing_accepted_issues(tmp_path, version):
    import copy
    from app.manifest import migrate_manifest
    from app.review import repair_instructions
    data = default_manifest()
    fixture_version = 3 if version == 3 else 2
    legacy = json.loads((Path(__file__).parent / f'fixtures/repair-instructions-v{fixture_version}.json').read_text(encoding="utf-8"))
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
    assert instructions['version'] == 7
    assert instructions['rules'] == repair_instructions()['rules'] + ['My additional rule']
    assert instructions['workflow']['eligible_statuses'] == ['open', 'fixed']
    assert instructions['workflow']['excluded_statuses'] == ['dismissed', 'verified']
    assert instructions['workflow']['scope'] == 'targeted_repairs_of_existing_output'
    assert instructions['note_handling'] == repair_instructions()['note_handling']
    assert instructions['custom'] == {'preserve': True}
    assert instructions['statuses']['custom'] == 'Keep this too'
    assert migrated['files'] == original['files']
    assert data == original
    assert migrate_manifest(migrated) == migrated


def test_note_contract_migration_preserves_custom_rules_and_notes(tmp_path):
    import copy
    from app.manifest import migrate_manifest
    from app.review import repair_instructions

    data = default_manifest()
    legacy = json.loads((Path(__file__).parent / 'fixtures/repair-instructions-v3.json').read_text(encoding='utf-8'))
    legacy['rules'][2] = 'Keep our custom handling of this note.'
    legacy['rules'].append('Keep our additional check.')
    legacy['workflow']['executor'] = 'custom-external-tool'
    data['repair_instructions'] = legacy
    data['files']['one.pdf'] = {'note': 'Keep this note.', 'custom': {'keep': True}}
    original = copy.deepcopy(data)
    migrated = migrate_manifest(data)
    instructions = migrated['repair_instructions']

    assert instructions['rules'][2] == legacy['rules'][2]
    assert instructions['rules'][-1] == 'Keep our additional check.'
    assert instructions['note_handling'] == repair_instructions()['note_handling']
    assert instructions['workflow']['executor'] == 'custom-external-tool'
    assert migrated['files'] == original['files']
    assert data == original
    save_manifest(tmp_path, migrated, expected_revision=None)
    assert load_manifest(tmp_path) == migrated


def test_v4_migration_removes_retired_defaults_without_losing_custom_data(monkeypatch):
    import copy
    import hashlib
    from app import review
    from app.manifest import migrate_manifest

    retired_rule = 'Retired built-in instruction.'
    retired_digest = hashlib.sha256(retired_rule.encode('utf-8')).hexdigest()
    monkeypatch.setattr(review, '_RETIRED_RULE_HASHES', review._RETIRED_RULE_HASHES | {retired_digest})
    data = default_manifest()
    instructions = data['repair_instructions']
    instructions['version'] = 4
    instructions.pop('note_handling')
    instructions['project_policy'] = {'obsolete': True}
    instructions['rules'].extend([retired_rule, 'My custom instruction.'])
    data['files']['one.pdf'] = {'note': 'User request.', 'custom': True}
    original = copy.deepcopy(data)

    migrated = migrate_manifest(data)
    assert migrated['repair_instructions']['version'] == 7
    assert 'project_policy' not in migrated['repair_instructions']
    assert retired_rule not in migrated['repair_instructions']['rules']
    assert migrated['repair_instructions']['rules'][-1] == 'My custom instruction.'
    assert migrated['repair_instructions']['note_handling'] == review.repair_instructions()['note_handling']
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

import copy
import os

import pytest

from app.api import BackendApi
from app.manifest import (ManifestError, ManifestFormatError, load_manifest,
                          manifest_revision, save_manifest, validate_manifest)
from tests.test_backend_api import create_pdf


def payload(document, accepted=True):
    return {'accepted': accepted, 'expected_sha256': document['ocr_sha256'],
            'expected_identity': document['identity_token']}


def test_acceptance_is_separate_persisted_revocable_and_bound_to_changed_bytes(tmp_path):
    path = tmp_path/'one.pdf'
    create_pdf(path, 'Before repair')
    api = BackendApi(tmp_path)
    try:
        doc = api.open_document('one.pdf')
        with pytest.raises(ValueError, match='OK'):
            api.set_repair_acceptance('one.pdf', payload(doc))
        api.set_review_complete('one.pdf', {'complete': True, 'expected_sha256': doc['ocr_sha256']})
        before = copy.deepcopy(load_manifest(tmp_path)['files']['one.pdf'])
        row = api.set_repair_acceptance('one.pdf', payload(doc))
        assert row['repairs_accepted'] and row['repair_accepted_at']
        saved = load_manifest(tmp_path)['files']['one.pdf']
        for field in ['note', 'issues', 'review_complete', 'review_completed_at', 'status']:
            assert saved[field] == before[field]
        assert saved['repair_acceptance']['ocr_sha256'] == doc['ocr_sha256']
        api.set_repair_acceptance('one.pdf', payload(doc))
        assert len(load_manifest(tmp_path)['files']['one.pdf']['repair_acceptance_history']) == 1
        api.open_folder(tmp_path)
        doc = api.open_document('one.pdf')
        assert doc['repairs_accepted']
        api.set_repair_acceptance('one.pdf', payload(doc, False))
        assert not load_manifest(tmp_path)['files']['one.pdf']['repair_acceptance']
        api.set_repair_acceptance('one.pdf', payload(doc))
        historical = copy.deepcopy(load_manifest(tmp_path)['files']['one.pdf']['repair_acceptance_history'])
        create_pdf(path, 'After repair, different PDF')
        with pytest.raises(ValueError, match='PDF se změnilo'):
            api.set_repair_acceptance('one.pdf', payload(doc))
        api.open_folder(tmp_path)
        assert not api.public_state()['files'][0]['repairs_accepted']
        current = api.open_document('one.pdf')
        assert not current['repairs_accepted']
        # Even an external repair writer updating identity cannot transfer acceptance.
        candidate = load_manifest(tmp_path)
        candidate['files']['one.pdf']['identity'] = api.files['one.pdf'].identity.to_dict()
        save_manifest(tmp_path, candidate, expected_revision=manifest_revision(tmp_path))
        api.open_folder(tmp_path)
        current = api.open_document('one.pdf')
        assert not current['repairs_accepted']
        assert load_manifest(tmp_path)['files']['one.pdf']['repair_acceptance_history'] == historical
        api.set_repair_acceptance('one.pdf', payload(current))
        assert load_manifest(tmp_path)['files']['one.pdf']['repair_acceptance']['ocr_sha256'] == current['ocr_sha256']
    finally:
        api.close()


def test_acceptance_conflict_rolls_back_and_preserves_external_note(tmp_path):
    create_pdf(tmp_path/'one.pdf', 'Sample')
    api = BackendApi(tmp_path)
    try:
        doc = api.open_document('one.pdf')
        api.set_review_complete('one.pdf', {'complete': True, 'expected_sha256': doc['ocr_sha256']})
        external = load_manifest(tmp_path)
        external['files']['one.pdf']['note'] = 'New human note'
        save_manifest(tmp_path, external, expected_revision=manifest_revision(tmp_path))
        with pytest.raises(ManifestError):
            api.set_repair_acceptance('one.pdf', payload(doc))
        assert 'repair_acceptance' not in api.manifest['files']['one.pdf']
        assert load_manifest(tmp_path)['files']['one.pdf']['note'] == 'New human note'
    finally:
        api.close()


def test_retained_marks_block_acceptance_and_never_change_status(tmp_path):
    create_pdf(tmp_path/'one.pdf', 'Sample')
    api = BackendApi(tmp_path)
    try:
        doc = api.open_document('one.pdf')
        api.set_review_complete('one.pdf', {'complete': True, 'expected_sha256': doc['ocr_sha256']})
        api.add_issue('one.pdf', {'page_index': 0, 'bbox': [30,30,70,70],
                                'kind': 'position', 'expected_sha256': doc['ocr_sha256']})
        with pytest.raises(ValueError, match='×'):
            api.set_repair_acceptance('one.pdf', payload(doc))
        assert api.manifest['files']['one.pdf']['issues'][0]['status'] == 'open'
    finally:
        api.close()


def test_acceptance_rejects_replacement_even_with_same_stat_identity(tmp_path):
    path = tmp_path/'one.pdf'
    create_pdf(path, 'Sample A')
    api = BackendApi(tmp_path)
    try:
        doc = api.open_document('one.pdf');stat = path.stat()
        create_pdf(path, 'Sample B')
        assert path.stat().st_size == stat.st_size
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with pytest.raises(ValueError, match='PDF se změnilo'):
            api.set_repair_acceptance('one.pdf', payload(doc))
    finally:
        api.close()


@pytest.mark.parametrize('record', [
    {'ocr_sha256': 'invalid', 'accepted_at': '2026-10-06T12:00:00+02:00'},
    {'ocr_sha256': 'a'*64, 'accepted_at': '2026-10-06T12:00:00'},
    {'ocr_sha256': 'a'*64, 'accepted_at': None},
])
def test_native_validator_rejects_invalid_acceptance(tmp_path, record):
    create_pdf(tmp_path/'one.pdf', 'Sample')
    api = BackendApi(tmp_path)
    try:
        api.open_document('one.pdf')
        candidate = copy.deepcopy(api.manifest)
        candidate['files']['one.pdf']['repair_acceptance'] = record
        with pytest.raises(ManifestFormatError):
            validate_manifest(candidate)
    finally:
        api.close()

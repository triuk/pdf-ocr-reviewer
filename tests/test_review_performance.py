"""Integrity requirements for compact responses and cheaper manifest transactions."""
import copy
import json
import os

import pymupdf
import pytest

from app.api import BackendApi
from app.manifest import ManifestWriteError, load_manifest, manifest_revision


@pytest.fixture
def review(tmp_path):
    pdf = tmp_path / 'one.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 50), 'Test word')
        doc.save(pdf)
    api = BackendApi(tmp_path)
    opened = api.open_document(pdf.name)
    api.manifest['custom'] = {'preserved': [1, {'value': 2}]}
    payload = {'page_index': 0, 'bbox': [20, 20, 100, 60], 'kind': 'position',
               'expected_sha256': opened['ocr_sha256']}
    first = api.add_issue(pdf.name, payload)['issue_id']
    second = api.add_issue(pdf.name, payload)['issue_id']
    try:
        yield api, pdf, payload, first, second
    finally:
        api.close()


@pytest.mark.parametrize('operation', ['issue', 'new_issue', 'file_note', 'options', 'position'])
def test_failed_copy_on_write_keeps_all_previous_objects_unchanged(review, monkeypatch, operation):
    api, pdf, payload, first, _ = review
    original = api.manifest
    before = copy.deepcopy(original)
    def fail(*args, **kwargs):
        raise ManifestWriteError('disk full')
    monkeypatch.setattr('app.api.save_manifest', fail)
    calls = {
        'issue': lambda: api.update_issue(pdf.name, first, {'note': 'new', 'expected_sha256': payload['expected_sha256']}),
        'new_issue': lambda: api.add_issue(pdf.name, payload),
        'file_note': lambda: api.set_file_note(pdf.name, 'new'),
        'options': lambda: api.set_ui_options({'zoom_percent': 130}),
        'position': lambda: api.set_last_page(pdf.name, 1),
    }
    with pytest.raises(ManifestWriteError):
        calls[operation]()
    assert api.manifest is original
    assert original == before


def test_compact_response_keeps_history_and_does_not_alias_manifest(review):
    api, pdf, payload, first, second = review
    original = copy.deepcopy(api.manifest)
    response = api.update_issue(pdf.name, first, {'note': 'new', 'expected_sha256': payload['expected_sha256']}, compact=True)
    assert 'issues' not in response
    assert response['issue']['id'] == first
    assert response['issue_counts']['open'] == 2
    assert response['issue']['history'][-1]['changes'] == {'note': 'new'}
    response['issue']['history'].clear()
    saved = load_manifest(pdf.parent)
    assert saved['files'][pdf.name]['issues'][1] == original['files'][pdf.name]['issues'][1]
    assert saved['custom'] == original['custom']
    assert api.manifest['files'][pdf.name]['issues'][0]['history']


def test_noop_does_not_write_or_backup_but_still_checks_external_revision(review, monkeypatch):
    from app.manifest import ManifestError, save_manifest
    api, pdf, payload, first, _ = review
    before = manifest_revision(pdf.parent)
    writes = []
    real_save = api._save_manifest
    monkeypatch.setattr(api, '_save_manifest', lambda: (writes.append(True), real_save()))
    api.set_last_page(pdf.name, 0)
    api.set_file_note(pdf.name, '')
    api.set_ui_options({'zoom_percent': 100})
    assert not writes
    assert manifest_revision(pdf.parent) == before
    external = load_manifest(pdf.parent)
    external['custom']['external'] = True
    save_manifest(pdf.parent, external, expected_revision=before)
    for action in [lambda: api.set_last_page(pdf.name, 0), lambda: api.set_file_note(pdf.name, ''),
                   lambda: api.set_ui_options({'zoom_percent': 100}),
                   lambda: api.update_issue(pdf.name, first, {'note': '', 'expected_sha256': payload['expected_sha256']})]:
        with pytest.raises(ManifestError, match='jiný nástroj'):
            action()
    assert load_manifest(pdf.parent)['custom']['external'] is True


def test_hash_check_rejects_same_size_and_timestamp_content_change(review):
    api, pdf, payload, first, _ = review
    stat = pdf.stat()
    raw = pdf.read_bytes()
    pdf.write_bytes(raw[:-1] + (b'X' if raw[-1:] != b'X' else b'Y'))
    os.utime(pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    before = copy.deepcopy(api.manifest)
    with pytest.raises(ValueError, match='PDF se změnilo'):
        api.update_issue(pdf.name, first, {'note': 'must not save', 'expected_sha256': payload['expected_sha256']})
    assert api.manifest == before

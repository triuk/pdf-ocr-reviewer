import json

import pytest

from app.drafts import DraftStore
from app.manifest import MANIFEST_FILENAME, ManifestError, default_manifest, load_manifest, list_backups, manifest_revision, restore_backup, save_manifest


def test_backups_are_bounded_valid_and_conflict_checked(tmp_path):
    data = default_manifest()
    revision = None
    for n in range(15):
        data['counter'] = n
        revision = save_manifest(tmp_path, data, expected_revision=revision)
    backups = list_backups(tmp_path)
    assert len(backups) == 10
    chosen = backups[0]['id']
    with pytest.raises(ManifestError, match='změnil'):
        restore_backup(tmp_path, chosen, expected_revision='0'*64)
    assert load_manifest(tmp_path)['counter'] == 14
    restore_backup(tmp_path, chosen, expected_revision=revision)
    assert load_manifest(tmp_path)['counter'] == 13
    prior = tmp_path / '.pdf-ocr-reviewer-backups' / 'before-restore.json'
    assert json.loads(prior.read_text())['counter'] == 14


def test_corrupt_manifest_restore_preserves_bad_bytes_and_valid_backup(tmp_path):
    data = default_manifest()
    rev = save_manifest(tmp_path, data, expected_revision=None)
    data['next'] = True
    save_manifest(tmp_path, data, expected_revision=rev)
    backup = list_backups(tmp_path)[0]['id']
    path = tmp_path / MANIFEST_FILENAME
    path.write_bytes(b'{broken')
    restore_backup(tmp_path, backup, expected_revision=manifest_revision(tmp_path))
    assert load_manifest(tmp_path)['schema_version'] == 2
    assert (tmp_path / '.pdf-ocr-reviewer-backups' / 'before-restore.json').read_bytes() == b'{broken'
    assert any(b['id'] == backup for b in list_backups(tmp_path))
    with pytest.raises(ManifestError):
        restore_backup(tmp_path, '../../elsewhere.json', expected_revision=manifest_revision(tmp_path))


def test_drafts_survive_restart_and_old_ack_does_not_remove_new_text(tmp_path):
    directory = tmp_path / 'state'
    folder = tmp_path / 'pdfs'
    folder.mkdir()
    first = {'folder':str(folder), 'fileId':'a.pdf','issueId':'i', 'note':'first', 'token':'old',
             'base_note':'saved','expected_sha256':'a'*64, 'kind':'text'}
    store = DraftStore(directory)
    store.put(first)
    newer = {**first, 'note':'newer', 'token':'new'}
    store.put(newer)
    store.remove('old')
    restored = DraftStore(directory)
    assert restored.list(folder) == [newer]
    assert restored.list(tmp_path / 'another-folder') == []
    restored.remove('new')
    assert restored.list(folder) == []


def test_bad_draft_database_is_not_silently_replaced(tmp_path):
    store = DraftStore(tmp_path)
    store.path.write_bytes(b'not sqlite')
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        store.list(tmp_path)
    assert store.path.read_bytes() == b'not sqlite'

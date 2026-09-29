import copy
import multiprocessing as mp
from pathlib import Path

import pytest

from app.api import BackendApi
from app.file_lock import file_lock
from app.manifest import ManifestError, ManifestFormatError, default_manifest, load_manifest, manifest_revision, save_manifest, validate_manifest


def competing_writer(folder, revision, start, ready, done, result):
    candidate = load_manifest(Path(folder))
    candidate['external'] = 'preserve'
    ready.set()
    start.wait(5)
    try:
        save_manifest(Path(folder), candidate, expected_revision=revision)
        result.put('written')
    except ManifestError:
        result.put('conflict')
    finally:
        done.set()


def hold_lock(path, ready):
    import time
    with file_lock(Path(path)):
        ready.set()
        time.sleep(60)


def test_writer_cannot_enter_between_compare_and_replace(tmp_path, monkeypatch):
    import app.manifest as module
    data = default_manifest()
    revision = save_manifest(tmp_path, data, expected_revision=None)
    ctx = mp.get_context('spawn')
    start, ready, done = (ctx.Event() for _ in range(3))
    result = ctx.Queue()
    child = ctx.Process(target=competing_writer, args=(str(tmp_path), revision, start, ready, done, result))
    child.start()
    try:
        assert ready.wait(5)
        write = module._write_manifest
        def write_while_other_process_waits(folder, candidate):
            start.set()
            assert not done.wait(0.2), 'Second writer passed the shared lock'
            return write(folder, candidate)
        monkeypatch.setattr(module, '_write_manifest', write_while_other_process_waits)
        data['ours'] = 'saved'
        save_manifest(tmp_path, data, expected_revision=revision)
        assert done.wait(5)
        assert result.get(timeout=2) == 'conflict'
        assert load_manifest(tmp_path)['ours'] == 'saved'
    finally:
        child.join(2)
        if child.is_alive():
            child.terminate()
            child.join(2)


def test_lock_timeout_and_process_death_release(tmp_path):
    path = tmp_path / 'writer.lock'
    ctx = mp.get_context('spawn')
    ready = ctx.Event()
    child = ctx.Process(target=hold_lock, args=(str(path), ready))
    child.start()
    try:
        assert ready.wait(5)
        with pytest.raises(TimeoutError):
            with file_lock(path, timeout=0.05):
                pass
    finally:
        child.terminate()
        child.join(5)
    with file_lock(path, timeout=0.2):
        assert path.exists()


@pytest.mark.parametrize('entry', [
    {'resources': None}, {'resources': {'qa2': []}}, {'identity': []},
    {'identity': {'size': -1, 'mtime_ns': 1}}, {'last_page': True},
    {'note': {}}, {'status': []}, {'problem_pages': [True]},
])
def test_bad_file_fields_have_path(entry):
    data = default_manifest()
    data['files']['a.pdf'] = entry
    with pytest.raises(ManifestFormatError, match=r"files\['a.pdf'\]"):
        validate_manifest(data)


@pytest.mark.parametrize('options', [
    {'zoom_percent': 200, 'ocr_mode': 'bad'}, {'overlay': 'false'},
    {'zoom_percent': None}, {'status_filter': []}, {'unknown': True},
])
def test_rejected_ui_patch_is_transactional(tmp_path, options):
    api = BackendApi(tmp_path)
    before = copy.deepcopy(api.manifest)
    with pytest.raises((ValueError, ManifestError)):
        api.set_ui_options(options)
    assert api.manifest == before
    assert manifest_revision(tmp_path) is None


def test_legacy_writer_instructions_preserve_extensions(tmp_path):
    from app.manifest import migrate_manifest
    data = default_manifest()
    instructions = data['repair_instructions']
    instructions['version'] = 1
    instructions.pop('writer_protocol')
    instructions['custom'] = {'keep': True}
    instructions['rules'].append('Custom rule')
    migrated = migrate_manifest(data)
    assert migrated['repair_instructions']['writer_protocol']['version'] == 1
    assert migrated['repair_instructions']['custom'] == {'keep': True}
    assert migrated['repair_instructions']['rules'][-1] == 'Custom rule'
    assert 'writer_protocol' not in data['repair_instructions']

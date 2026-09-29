import json
import shutil

import pymupdf
import pytest

from app.api import BackendApi
from app.pdf_document import PdfDocumentError


def create_pdf(path):
    with pymupdf.open() as doc:
        doc.new_page().insert_text((30, 50), 'sample')
        doc.save(path)


class Event:
    def __init__(self, *args):
        self.args = args
        self.result = None
    def get_string_at(self, index):
        return self.args[index]
    def return_string(self, result):
        self.result = json.loads(result)


def test_failed_open_preserves_active_document(tmp_path):
    create_pdf(tmp_path / 'a.pdf')
    (tmp_path / 'bad.pdf').write_bytes(b'bad')
    api = BackendApi(tmp_path)
    original = api.open_document('a.pdf')
    try:
        with pytest.raises(PdfDocumentError):
            api.open_document('bad.pdf')
        assert api.active_file_id == 'a.pdf'
        assert api.document_id == original['document_id']
        assert api.render_page_packet('x', 'a.pdf', 0, 300)
    finally:
        api.close()


def test_stale_folder_and_document_callbacks_do_not_write(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir(); second.mkdir()
    create_pdf(first / 'a.pdf'); shutil.copyfile(first / 'a.pdf', second / 'a.pdf')
    api = BackendApi(first)
    api.open_document('a.pdf')
    old = json.dumps({'context_id':api.context_id, 'document_id':api.document_id})
    api.open_folder(second); api.open_document('a.pdf')
    callback = api._context_callback(api.set_file_note_callback, 2, True)
    event = Event('a.pdf', 'wrong folder', old)
    callback(event)
    assert event.result['error']['code'] == 'STALE_CONTEXT'
    assert api.manifest['files']['a.pdf']['note'] == ''
    current = json.dumps({'context_id':api.context_id, 'document_id':api.document_id})
    event = Event('a.pdf', 'right folder', current)
    callback(event)
    assert event.result['ok']
    api.close()

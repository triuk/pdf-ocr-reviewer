from __future__ import annotations

from pathlib import Path

import pymupdf

from app.api import BackendApi
from app.manifest import MANIFEST_FILENAME, load_manifest
from app.raw_packet import unpack_raw_packet


def create_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    page = document.new_page(width=400, height=600)
    page.insert_text((40, 60), text, fontsize=14)
    document.save(path)
    document.close()


def test_backend_folder_document_packet_and_manifest(tmp_path: Path) -> None:
    create_pdf(tmp_path / "one.pdf", "OCR sample")
    create_pdf(tmp_path / "two.pdf", "Second PDF")
    api = BackendApi()
    try:
        public = api.open_folder(tmp_path)
        assert [item["file_id"] for item in public["files"]] == ["one.pdf", "two.pdf"]

        document = api.open_document("one.pdf")
        assert document["page_count"] == 1
        assert (tmp_path / MANIFEST_FILENAME).exists()

        packet = api.render_page_packet("request-1", "one.pdf", 0, 800)
        header, image = unpack_raw_packet(packet)
        assert header["request_id"] == "request-1"
        assert header["file_id"] == "one.pdf"
        assert header["pixel_width"] == 800
        assert "OCR sample" in header["ocr"]["pdf_order"]
        assert image.startswith(b"\x89PNG\r\n\x1a\n")

        api.set_file_status("one.pdf", "error")
        api.toggle_problem_page("one.pdf", 0)
        api.set_last_page("one.pdf", 0)
        api.set_file_note("one.pdf", "Wrong character")
        api.set_ui_options({"ocr_mode": "pdf_order", "overlay": True, "zoom_percent": 120})

        manifest = load_manifest(tmp_path)
        entry = manifest["files"]["one.pdf"]
        assert entry["status"] == "error"
        assert entry["problem_pages"] == [0]
        assert entry["note"] == "Wrong character"
        assert manifest["ui"]["ocr_mode"] == "pdf_order"
        assert manifest["ui"]["overlay"] is True
        assert manifest["ui"]["zoom_percent"] == 120

        csv_text = api.export_csv()
        assert "file,status,changed_since_review" in csv_text
        assert "one.pdf,error,false,1,Wrong character" in csv_text
    finally:
        api.close()


def test_open_document_remains_available_when_manifest_write_fails(
    tmp_path: Path, monkeypatch
) -> None:
    create_pdf(tmp_path / "readonly.pdf", "Readable OCR")
    api = BackendApi()
    api.open_folder(tmp_path)

    from app import api as api_module
    from app.manifest import ManifestWriteError

    def fail_save(folder, manifest) -> None:
        raise ManifestWriteError("simulated read-only folder")

    monkeypatch.setattr(api_module, "save_manifest", fail_save)
    try:
        document = api.open_document("readonly.pdf")
        assert document["page_count"] == 1
        assert document["persistence_error"]["code"] == "MANIFEST_WRITE_FAILED"
        packet = api.render_page_packet("request-readonly", "readonly.pdf", 0, 600)
        header, image = unpack_raw_packet(packet)
        assert header["file_id"] == "readonly.pdf"
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        api.close()

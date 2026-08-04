from __future__ import annotations

from pathlib import Path

import pymupdf

from app.pdf_document import PdfDocument


def create_test_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.insert_text((30, 50), "First OCR line", fontsize=12)
    page.insert_text((30, 90), "Second line", fontsize=12)
    document.save(path)
    document.close()


def test_pdf_metadata_and_render(tmp_path: Path) -> None:
    path = tmp_path / "test.pdf"
    create_test_pdf(path)

    with PdfDocument(path) as document:
        metadata = document.page_metadata()
        rendered = document.render_page(0, 600)

    assert len(metadata) == 1
    assert metadata[0].width == 300
    assert metadata[0].height == 400
    assert rendered.pixel_width == 600
    assert rendered.pixel_height == 800
    assert rendered.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert "First OCR line" in rendered.ocr["pdf_order"]
    assert [item["text"] for item in rendered.ocr["layout_items"]][:3] == ["First", "OCR", "line"]

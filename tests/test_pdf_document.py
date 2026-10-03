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


def test_extreme_aspect_ratios_and_high_zoom_have_bounded_rasters(tmp_path):
    from app.pdf_document import MAX_RENDER_PIXELS, MAX_RENDER_SIDE
    path = tmp_path / 'extreme.pdf'
    with pymupdf.open() as doc:
        for width, height in [(100, 10000), (10000, 100), (600, 850)]:
            page = doc.new_page(width=width, height=height)
            page.insert_text((10, 30), 'OCR')
        doc.save(path)
    with PdfDocument(path) as document:
        for page in range(3):
            rendered = document.render_page(page, 4000)
            assert rendered.pixel_width * rendered.pixel_height <= MAX_RENDER_PIXELS
            assert max(rendered.pixel_width, rendered.pixel_height) <= MAX_RENDER_SIDE
            assert rendered.pixel_width >= 1 and rendered.pixel_height >= 1
            assert 'OCR' in rendered.ocr['pdf_order']

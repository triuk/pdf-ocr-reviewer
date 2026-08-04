from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from .models import PageMetadata


class PdfDocumentError(RuntimeError):
    """Raised when a PDF cannot be opened, inspected, or rendered."""


@dataclass(frozen=True, slots=True)
class RenderedPage:
    page_index: int
    pixel_width: int
    pixel_height: int
    image_bytes: bytes
    mime_type: str
    ocr: dict[str, Any]


class PdfDocument:
    def __init__(self, path: Path):
        self.path = path
        try:
            self._document = pymupdf.open(path)
        except Exception as exc:
            raise PdfDocumentError(f"PDF cannot be opened: {path.name}") from exc
        if self._document.needs_pass:
            self._document.close()
            raise PdfDocumentError(f"PDF requires a password: {path.name}")

    def close(self) -> None:
        self._document.close()

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        return self._document.page_count

    def page_metadata(self) -> list[PageMetadata]:
        metadata: list[PageMetadata] = []
        for page_index in range(self.page_count):
            page = self._document.load_page(page_index)
            rect = page.rect
            metadata.append(
                PageMetadata(
                    page_index=page_index,
                    width=float(rect.width),
                    height=float(rect.height),
                )
            )
        return metadata

    def render_page(self, page_index: int, target_width: int) -> RenderedPage:
        if page_index < 0 or page_index >= self.page_count:
            raise PdfDocumentError(f"Page index is out of range: {page_index}")
        if target_width < 200 or target_width > 4000:
            raise PdfDocumentError(f"Unsupported render width: {target_width}")

        try:
            page = self._document.load_page(page_index)
            rect = page.rect
            scale = target_width / rect.width
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            image_bytes = pixmap.tobytes("png")
            words = page.get_text("words", sort=False)
            pdf_order = page.get_text("text", sort=False)
            geometric_order = page.get_text("text", sort=True)
        except Exception as exc:
            raise PdfDocumentError(
                f"Page {page_index + 1} cannot be rendered: {self.path.name}"
            ) from exc

        layout_items = [
            {
                "x0": float(word[0]),
                "y0": float(word[1]),
                "x1": float(word[2]),
                "y1": float(word[3]),
                "text": str(word[4]),
                "block": int(word[5]),
                "line": int(word[6]),
                "word": int(word[7]),
            }
            for word in words
        ]
        ocr = {
            "page_width": float(rect.width),
            "page_height": float(rect.height),
            "layout_items": layout_items,
            "pdf_order": pdf_order,
            "geometric_order": geometric_order,
        }
        return RenderedPage(
            page_index=page_index,
            pixel_width=pixmap.width,
            pixel_height=pixmap.height,
            image_bytes=image_bytes,
            mime_type="image/png",
            ocr=ocr,
        )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from .models import PageMetadata
from .review import COORDINATE_SYSTEM, validate_bbox


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
            layout_items = self._layout_items(page)
            pdf_order = page.get_text("text", sort=False)
            geometric_order = page.get_text("text", sort=True)
        except Exception as exc:
            raise PdfDocumentError(
                f"Page {page_index + 1} cannot be rendered: {self.path.name}"
            ) from exc

        ocr = {
            "page_width": float(rect.width),
            "page_height": float(rect.height),
            "layout_items": layout_items,
            "pdf_order": pdf_order,
            "geometric_order": geometric_order,
            "rotation": page.rotation,
            "coordinate_system": COORDINATE_SYSTEM,
        }
        return RenderedPage(
            page_index=page_index,
            pixel_width=pixmap.width,
            pixel_height=pixmap.height,
            image_bytes=image_bytes,
            mime_type="image/png",
            ocr=ocr,
        )

    @staticmethod
    def _layout_items(page: Any) -> list[dict[str, Any]]:
        items = []
        for word in page.get_text("words", sort=False):
            rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
            items.append({
                "x0": float(rect.x0), "y0": float(rect.y0),
                "x1": float(rect.x1), "y1": float(rect.y1),
                "text": str(word[4]), "block": int(word[5]),
                "line": int(word[6]), "word": int(word[7]),
            })
        return items

    def region_snapshot(self, page_index: int, bbox: list[float]) -> dict[str, Any]:
        if type(page_index) is not int or not 0 <= page_index < self.page_count:
            raise ValueError("Invalid page index.")
        page = self._document.load_page(page_index)
        validate_bbox(bbox, page.rect.width, page.rect.height)
        x0, y0, x1, y1 = bbox
        targets = [item for item in self._layout_items(page)
                   if item["x0"] < x1 and item["x1"] > x0
                   and item["y0"] < y1 and item["y1"] > y0]
        return {
            "page_index": page_index, "bbox": bbox,
            "page_width": page.rect.width, "page_height": page.rect.height,
            "page_rotation": page.rotation, "coordinate_system": COORDINATE_SYSTEM,
            "targets": targets, "text": " ".join(item["text"] for item in targets),
        }

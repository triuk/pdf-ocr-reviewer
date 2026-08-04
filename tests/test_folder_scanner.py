from __future__ import annotations

from pathlib import Path

from app.folder_scanner import scan_pdf_folder


def test_scanner_returns_only_direct_pdf_files(tmp_path: Path) -> None:
    (tmp_path / "B.PDF").write_bytes(b"b")
    (tmp_path / "a.pdf").write_bytes(b"aa")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.pdf").write_bytes(b"x")

    files = scan_pdf_folder(tmp_path)

    assert [item.name for item in files] == ["a.pdf", "B.PDF"]
    assert files[0].identity.size == 2

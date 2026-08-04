from __future__ import annotations

from pathlib import Path

from .models import FileIdentity, ScannedPdf


class FolderScanError(RuntimeError):
    """Raised when a folder cannot be scanned safely."""


def scan_pdf_folder(folder: Path) -> list[ScannedPdf]:
    resolved = folder.expanduser().resolve()
    if not resolved.exists():
        raise FolderScanError(f"Folder does not exist: {resolved}")
    if not resolved.is_dir():
        raise FolderScanError(f"Path is not a folder: {resolved}")

    try:
        entries = list(resolved.iterdir())
    except OSError as exc:
        raise FolderScanError(f"Folder cannot be read: {resolved}") from exc

    pdf_files: list[ScannedPdf] = []
    for path in entries:
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            raise FolderScanError(f"Cannot read file metadata: {path.name}") from exc
        pdf_files.append(
            ScannedPdf(
                file_id=path.name,
                name=path.name,
                path=path,
                identity=FileIdentity(size=stat.st_size, mtime_ns=stat.st_mtime_ns),
            )
        )

    pdf_files.sort(key=lambda item: (item.name.casefold(), item.name))
    return pdf_files

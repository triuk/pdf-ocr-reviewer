from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from app.application import PdfOcrReviewerApplication, get_ui_folder
from app.pdf_document import PdfDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdf-ocr-reviewer",
        description="Review PDF page images and OCR layers side by side.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        help="Open this folder when the application starts.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Check packaged runtime dependencies and exit.",
    )
    parser.add_argument("--manifest-revision", action="store_true", help="Print the current manifest SHA-256 or missing.")
    parser.add_argument("--write-manifest", type=Path, help="Validate and commit a candidate manifest with a revision check.")
    parser.add_argument("--expected-revision", help="SHA-256 from before reading the manifest, or missing.")
    return parser.parse_args()


def _report(message: str) -> None:
    stream = sys.stdout
    if stream is not None:
        stream.write(message + "\n")
        stream.flush()


def run_self_test() -> int:
    checks: list[tuple[str, bool]] = []

    try:
        import pymupdf

        checks.append(("PyMuPDF import", True))
    except Exception:
        checks.append(("PyMuPDF import", False))
        pymupdf = None  # type: ignore[assignment]

    try:
        from webui import webui  # noqa: F401

        checks.append(("WebUI import", True))
    except Exception:
        checks.append(("WebUI import", False))

    try:
        import tkinter

        tcl = tkinter.Tcl()
        tk_runtime_ok = bool(tcl.eval("info patchlevel"))
        checks.append(("Tk/Tcl runtime", tk_runtime_ok))
    except Exception:
        checks.append(("Tk/Tcl runtime", False))

    ui_folder = get_ui_folder()
    required_ui_files = (
        "index.html",
        "index.css",
        "state.js",
        "files.js",
        "document.js",
        "pages.js",
        "issues.js",
        "recovery.js",
        "workflow.js",
    )
    checks.append(
        (
            "UI assets",
            ui_folder.is_dir()
            and all((ui_folder / file_name).is_file() for file_name in required_ui_files),
        )
    )

    pdf_backend_ok = False
    if pymupdf is not None:
        try:
            with tempfile.TemporaryDirectory(prefix="pdf-ocr-reviewer-self-test-") as temp_dir:
                pdf_path = Path(temp_dir) / "self-test.pdf"
                document = pymupdf.open()
                page = document.new_page(width=300, height=400)
                page.insert_text((36, 72), "pdf-ocr-reviewer self-test")
                document.save(pdf_path)
                document.close()

                with PdfDocument(pdf_path) as pdf_document:
                    rendered = pdf_document.render_page(0, 600)
                    pdf_backend_ok = (
                        pdf_document.page_count == 1
                        and rendered.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                        and "pdf-ocr-reviewer" in rendered.ocr["pdf_order"]
                    )
        except Exception:
            pdf_backend_ok = False
    checks.append(("PDF render backend", pdf_backend_ok))

    failed = False
    for label, ok in checks:
        _report(f"{label}: {'OK' if ok else 'FAILED'}")
        failed = failed or not ok

    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    if args.manifest_revision or args.write_manifest:
        from app.manifest import ManifestError, manifest_revision, save_manifest
        from app.review import valid_hash
        try:
            if args.folder is None or not args.folder.is_dir():
                raise ValueError("--folder must name an existing folder.")
            if args.manifest_revision and args.write_manifest:
                raise ValueError("Choose either --manifest-revision or --write-manifest.")
            if args.manifest_revision:
                _report(manifest_revision(args.folder) or "missing")
            else:
                if args.expected_revision != "missing" and not valid_hash(args.expected_revision):
                    raise ValueError("--expected-revision must be a SHA-256 or missing.")
                candidate = json.loads(args.write_manifest.read_text(encoding="utf-8"))
                revision = save_manifest(args.folder, candidate, expected_revision=None if args.expected_revision == "missing" else args.expected_revision)
                _report(revision)
            return 0
        except (ManifestError, ValueError, OSError) as exc:
            _report(str(exc))
            return 2
    if args.self_test:
        return run_self_test()

    app = PdfOcrReviewerApplication(initial_folder=args.folder)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from app.application import PdfOcrReviewerApplication


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = PdfOcrReviewerApplication(initial_folder=args.folder)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

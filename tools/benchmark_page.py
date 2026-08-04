from __future__ import annotations

import argparse
import time
import tracemalloc
from pathlib import Path

from app.api import BackendApi
from app.raw_packet import unpack_raw_packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark one rendered PDF page packet.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1, help="One-based page number.")
    parser.add_argument("--width", type=int, default=1200, help="Rendered pixel width.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF does not exist: {pdf}")
    if args.page < 1:
        raise SystemExit("Page number must be at least 1.")

    api = BackendApi()
    try:
        api.open_folder(pdf.parent)
        api.open_document(pdf.name)
        tracemalloc.start()
        started = time.perf_counter()
        packet = api.render_page_packet(
            request_id="benchmark",
            file_id=pdf.name,
            page_index=args.page - 1,
            target_width=args.width,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        header, image = unpack_raw_packet(packet)
        json_header_bytes = len(packet) - len(image) - 4

        print(f"PDF: {pdf}")
        print(f"Page: {args.page}")
        print(f"Rendered size: {header['pixel_width']} x {header['pixel_height']} px")
        print(f"OCR words: {len(header['ocr']['layout_items'])}")
        print(f"JSON header: {json_header_bytes} bytes")
        print(f"PNG payload: {len(image)} bytes")
        print(f"Total packet: {len(packet)} bytes")
        print(f"Elapsed: {elapsed_ms:.3f} ms")
        print(f"Tracemalloc peak: {peak_bytes} bytes")
    finally:
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

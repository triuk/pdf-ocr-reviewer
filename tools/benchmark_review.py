"""Reproducible review benchmark; all writes are confined to temporary copies.

Run: python tools/benchmark_review.py --output /tmp/review-before.json
Optional --pdf copies an existing PDF instead of creating a large synthetic scan.
Timings include JSON responses and real atomic writes/backups, but not browser DOM.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
import app.api as api_module
import app.manifest as manifest_module
from app.api import BackendApi
from app.manifest import MANIFEST_FILENAME
from app.raw_packet import unpack_raw_packet


class Event:
    def __init__(self, *args):
        self.args = args
        self.response = ''

    def get_string(self):
        return self.args[0]

    def get_string_at(self, index):
        return self.args[index]

    def return_string(self, value):
        self.response = value


def synthetic_pdf(path, pages):
    rng = random.Random(42)
    with pymupdf.open() as doc:
        for index in range(pages):
            page = doc.new_page(width=600, height=800)
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, rng.randbytes(600 * 800 * 3), False)
            page.insert_image(page.rect, pixmap=pixmap)
            for line in range(30):
                page.insert_text((30, 40 + line * 20), f'Page {index + 1}: OCR review benchmark line {line + 1}', fontsize=10)
        doc.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--pages', type=int, default=60)
    parser.add_argument('--issues', type=int, default=1000)
    parser.add_argument('--history', type=int, default=20)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if min(args.pages, args.issues, args.history, args.samples) < 1:
        parser.error('Counts must be positive')
    with tempfile.TemporaryDirectory(prefix='ocr-review-benchmark-') as root:
        folder = Path(root)
        pdf = folder / 'benchmark-ocr.pdf'
        if args.pdf:
            shutil.copyfile(args.pdf, pdf)
        else:
            synthetic_pdf(pdf, args.pages)
        os.environ['PDF_OCR_REVIEWER_STATE_DIR'] = str(folder / 'state')
        api = BackendApi(folder)
        try:
            opened = api.open_document(pdf.name)
            api.add_issue(pdf.name, {'page_index': 0, 'bbox': [10, 10, 20, 20],
                                    'kind': 'position', 'expected_sha256': opened['ocr_sha256']})
            template = api.manifest['files'][pdf.name]['issues'][0]
            history = [{'action': 'edited', 'at': '2026-10-03T12:00:00+02:00',
                        'previous': {'note': 'Prior review note ' + str(i)},
                        'changes': {'note': 'Next review note ' + str(i)}} for i in range(args.history)]
            issues = []
            for index in range(args.issues):
                issue = copy.deepcopy(template)
                issue.update(id=f'benchmark-{index}', history=copy.deepcopy(history))
                issues.append(issue)
            api.manifest['files'][pdf.name]['issues'] = issues
            api._save_manifest()
            report = {'environment': {'python': platform.python_version(), 'pymupdf': pymupdf.VersionBind,
                                      'platform': platform.platform()},
                      'fixture': {'source': args.pdf.name if args.pdf else 'synthetic RGB noise scans, seed 42',
                                  'pdf_bytes': pdf.stat().st_size, 'pages': api.active_document.page_count,
                                  'manifest_bytes': (folder / MANIFEST_FILENAME).stat().st_size,
                                  'issues': args.issues, 'history_per_issue': args.history,
                                  'samples': args.samples}, 'operations': {}}

            def measure(name, operation):
                counters = defaultdict(lambda: {'calls': 0, 'ms': 0.0})
                def measured(fn, key):
                    def run(*a, **kw):
                        started = time.perf_counter()
                        try:
                            return fn(*a, **kw)
                        finally:
                            counters[key]['calls'] += 1
                            counters[key]['ms'] += (time.perf_counter() - started) * 1000
                    return run
                durations, sizes = [], []
                with ExitStack() as stack:
                    for module, attr, key in [(api_module, 'file_sha256', 'pdf_hash'),
                                              (api_module, 'save_manifest', 'manifest_save'),
                                              (manifest_module, '_backup_current', 'backup'),
                                              (api, '_issue_state', 'full_issue_state')]:
                        stack.enter_context(patch.object(module, attr, measured(getattr(module, attr), key)))
                    for i in range(args.samples):
                        start = time.perf_counter()
                        response = operation(i)
                        durations.append((time.perf_counter() - start) * 1000)
                        sizes.append(len(response))
                report['operations'][name] = {'median_ms': round(statistics.median(durations), 2),
                    'max_ms': round(max(durations), 2), 'response_bytes': round(statistics.mean(sizes)),
                    'components_per_sample': {key: {'calls': val['calls'] / args.samples,
                        'ms': round(val['ms'] / args.samples, 2)} for key, val in counters.items()}}
                print(name, report['operations'][name], flush=True)

            def callback(fn, *values):
                event = Event(*values)
                fn(event)
                result = json.loads(event.response)
                assert result['ok'], result
                return event.response.encode('utf-8')

            measure('issue_note', lambda i: callback(api.update_issue_callback, pdf.name, 'benchmark-0',
                json.dumps({'note': f'Autosave {i}', 'expected_sha256': opened['ocr_sha256']})))
            measure('file_note', lambda i: callback(api.set_file_note_callback, pdf.name, f'File note {i}'))
            measure('ui_option', lambda i: callback(api.set_ui_options_callback, json.dumps({'zoom_percent': 100 + i})))
            measure('same_page_position', lambda i: json.dumps(api.set_last_page(pdf.name, 0)).encode())
            measure('pdf_hash_only', lambda i: api_module.file_sha256(pdf).encode())
            measure('render_1200', lambda i: api.render_page_packet(str(i), pdf.name, 0, 1200))
            measure('render_2400', lambda i: api.render_page_packet(str(i), pdf.name, 0, 2400))
            packet = api.render_page_packet('size', pdf.name, 0, 2400)
            header, _ = unpack_raw_packet(packet)
            report['fixture']['raster_2400_pixels'] = header['pixel_width'] * header['pixel_height']
            args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        finally:
            api.close()


if __name__ == '__main__':
    main()

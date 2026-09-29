"""Create clearly labelled, disposable PDFs and review states for user acceptance."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pymupdf
from app.api import BackendApi
from app.manifest import load_manifest, manifest_revision, save_manifest
from app.pdf_document import PdfDocument


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit('Use a new destination; existing test data will not be overwritten.')
    args.destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='ocr-demo-state-') as state:
        os.environ['PDF_OCR_REVIEWER_STATE_DIR'] = state
        for index in range(1, 4):
            target = args.destination / f'{index:02d}-zkusebni-kopie.pdf'
            if args.source:
                shutil.copyfile(args.source, target)
            else:
                with pymupdf.open() as doc:
                    page = doc.new_page(width=600, height=800)
                    for line in range(25):
                        page.insert_text((50, 80 + line * 22), f'OCR review example line {line + 1}', fontsize=14)
                    doc.save(target)
        api = BackendApi(args.destination)
        for file_id in list(api.files):
            opened = api.open_document(file_id)
            api.set_file_note(file_id, 'Zkušební kopie pro test ovládání. Barevné stavy jsou ukázkové; OCR zde nebylo opravováno.')
            with PdfDocument(args.destination / file_id) as doc:
                words = doc.render_page(0, 600).ocr['layout_items']
            for n, kind in enumerate(('position', 'oversized', 'text')):
                word = words[min(n * 12, len(words) - 1)] if words else None
                bbox = [word[k] for k in ('x0','y0','x1','y1')] if word else [30, 30 + n*50, 180, 65 + n*50]
                api.add_issue(file_id, {'page_index':0,'bbox':bbox,'kind':kind,'expected_sha256':opened['ocr_sha256'],
                                       'note':'Ukázková připomínka pro test ovládání.'})
        api.close()
        revision = manifest_revision(args.destination)
        manifest = load_manifest(args.destination)
        names = sorted(manifest['files'])
        for index, name in enumerate(names):
            entry = manifest['files'][name]
            for n, issue in enumerate(entry['issues']):
                status = ('open', 'fixed', 'verified')[n] if index != 1 else ('fixed', 'fixed', 'open')[n]
                issue['status'] = status
                if status != 'open':
                    issue['result'] = {'summary':'Ukázkový stav pro test ergonomie; OCR nebylo opravováno.',
                                       'before_sha256':entry['ocr_sha256'],'after_sha256':entry['ocr_sha256'],'at':issue['created_at']}
                    issue['history'].append({'at':issue['created_at'],'action':'demo_status','to':status})
        manifest['ui'].update(last_file=names[0], issue_filter='all', ocr_mode='layout', zoom_percent=100)
        save_manifest(args.destination, manifest, expected_revision=revision)
    (args.destination / 'CTETE.txt').write_text('ZKUŠEBNÍ KOPIE — původní PDF se nemění.\nStavy oprav jsou simulované pro test ovládání, nikoli doklad provedených OCR oprav.\nV: zahájit ověření, C: potvrdit a další, R: vrátit připomínku, M: označovat, J/K: další/předchozí místo.\n', encoding='utf-8')
    print(args.destination.resolve())


if __name__ == '__main__':
    main()

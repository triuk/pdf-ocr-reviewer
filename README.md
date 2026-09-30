# pdf-ocr-reviewer

A local desktop application for fast visual review of OCR layers across a larger number of PDF files. The interface runs through WebUI, the backend is written in Python, and PDFs are processed with PyMuPDF.

## Current status

A functional prototype is implemented:

- loading a folder and its PDF list;
- opening a document and progressively loading visible pages;
- side-by-side display of the scan and OCR layer;
- OCR layout, PDF order, and geometric order modes;
- OCR overlay;
- image-only zoom with Ctrl + wheel and middle-button pan;
- whole-file review completion, problem pages, notes, and last position;
- atomically written `pdf-ocr-reviewer.manifest.json`;
- backups and CSV export under **Další**;
- one-click OCR word marks and drag-to-mark regions, with autosaved notes;
- red/new and blue/repaired regions; keep a mark for another external pass or delete it with ×;
- schema-2 manifest with repair instructions, SHA-256 anchors, QA references and issue history;
- explicit reload of external repairs and protection against overwriting a changed manifest;
- automated backend tests;
- automated one-file builds for Linux x86_64 and Windows x86_64 through GitHub Actions.

## Prebuilt binary

Every push to `main` runs the tests and creates two separate one-file artifacts in GitHub Actions:

- `pdf-ocr-reviewer-linux-x86_64`
- `pdf-ocr-reviewer-windows-x86_64.exe`

After downloading, the Linux binary only needs the executable bit:

```bash
chmod +x pdf-ocr-reviewer-linux-x86_64
./pdf-ocr-reviewer-linux-x86_64
```

Before launching the system browser, the Linux one-file build temporarily restores the original `LD_LIBRARY_PATH` saved by PyInstaller in `LD_LIBRARY_PATH_ORIG`. This prevents the system Firefox/Chromium process from loading incompatible shared libraries from the one-file bundle's temporary directory. After the browser starts, the application restores its own PyInstaller environment.

When a `v*` tag is created, for example `v0.1.0`, the same workflow automatically creates a GitHub Release after successful tests and builds. The release contains both one-file binaries and `SHA256SUMS.txt`.

Every built binary runs its own self-test before publication:

```bash
pdf-ocr-reviewer --self-test
```

The self-test verifies the PyMuPDF and WebUI imports, the Tk/Tcl runtime, the bundled UI assets, and the actual creation, opening, and rendering of a test PDF.

## Running from source

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

Optionally open a folder at startup:

```bash
python main.py --folder "/path/to/pdf-folder"
```

Self-test of the source installation:

```bash
python main.py --self-test
```

Tests:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

## Whole-file review

**OK**, next to each filename in the left list, records that you have finished
inspecting that PDF, even if issues remain. It saves immediately without opening
or switching documents. Clicking the filename still opens the PDF. The sidebar
filters and counts distinguish completed and unfinished inspections; issue counts
remain separate. **Obnovit** reloads external changes. Backups and CSV export are
under **Další**, which closes after selection, an outside click or Escape.

`review_complete` and `review_completed_at` store completion without overwriting
legacy `status` or annotations. Older `ok` files start checked; `error`,
`needs_review` and `unreviewed` start unchecked. Explicitly unchecking overrides
that initial mapping. Legacy classification stays in the manifest and CSV.
The old 0–3 classification shortcuts and automatic status advancement are retired.

## Targeted OCR repairs

Press **M** (or **Označovat**) to mark words with a click or regions with a drag.
Choose the problem type once; the application remembers it. Marks save immediately;
an optional note saves automatically. **Shift + drag** creates a region over an
existing mark. **Esc** returns to ordinary text selection. In Layout mode you can
also mark the spatial OCR pane.

**Ctrl + mouse wheel** over the scan zooms the image around the cursor (25–400%).
The OCR column and controls keep their size. Drag with the **middle mouse button**
to pan the magnified image, including in marking mode. **F** or clicking the zoom
percentage resets to 100%. The slider also controls only the image. Zoom is paused
while drawing a region; image marks keep their original PDF coordinates.

The sidebar shows counts and a filterable list. **J/K** move between marks and
**N** focuses the selected mark's note; **X** deletes the selected mark, like its
box cross, and selects the next mark in the current PDF/filter. At the end it
wraps to the first remaining mark; deleting the final one clears the selection.
Red means **K opravě**, blue means **Po opravě**.
After checking an external repair, delete a satisfactory mark with the **× directly
on its box**. Leave an unsatisfactory mark in place for the next external pass;
no confirmation or reopening is needed. Both red and blue marks remain repair
requests until deleted. Symbols and labels accompany the colors.

Deleted marks remain recoverable in **Archiv → Obnovit označení**. Older confirmed
marks are also archived and excluded from repairs. Restoring a mark never changes
PDF bytes. **Špatná velikost boxu** covers boxes that are too large or too small.

Everything is saved in `pdf-ocr-reviewer.manifest.json`. Older manifests and built-in instructions
are migrated on save, preserving marks, history and custom extensions. The first member, `repair_instructions`, describes the complete
repair contract, so a tool with access to the folder can receive this short prompt:

> Podle `pdf-ocr-reviewer.manifest.json` oprav otevřené připomínky u PDF od `XXX.pdf` po `YYY.pdf` včetně.

The reviewer does not run OCR or modify PDFs itself. The manifest is the control
file for the external tool. Each requested pass includes all retained `open` and
`fixed` marks within the inclusive filename range, once per pass. After an external repair,
click **Obnovit** to reread both the manifest and the PDF. External writers use the shared revision-checked writer described in the
manifest instructions; a changed revision is rejected under the writer lock. Unsaved notes are journaled locally and can be recovered after restart;
the recovery panel compares them with the current manifest before applying them. A stale PDF anchor is visibly flagged: mark
the current location again and cancel the obsolete mark. QA PASS reports remain
evidence only for the PDF hash they originally checked.

See [region review and the repair format](docs/region-review.md). Optional browser
verification uses real WebUI, Chromium and ChromeDriver on a temporary PDF copy:

```bash
python tools/smoke_region_review.py --pdf /path/to/sample-ocr.pdf
```

## Local one-file build

```bash
python -m pip install -r requirements-build.txt
python main.py --self-test
pyinstaller --noconfirm --clean pdf-ocr-reviewer.spec
```

The result is `dist/pdf-ocr-reviewer` on Linux or `dist/pdf-ocr-reviewer.exe` on Windows.

## Documentation and continued development

- [Goal, technical decisions, and startup](docs/product-overview.md)
- [WebUI reference and adopted patterns](docs/webui-reference.md)
- [User interface overview](docs/ui-overview.md)
- [Left column and shared scroll](docs/ui-columns-and-scroll.md)
- [OCR modes and keyboard controls](docs/ui-ocr-and-controls.md)
- [Region review and the repair manifest](docs/region-review.md)
- [Project structure](docs/project-structure.md)
- [Backend API](docs/backend-api.md)
- [Rendered page transport](docs/page-transport.md)
- [Implementation plan, tests, work status, and next steps](docs/implementation-plan.md)
- [Post-review work plan (2026-09-29)](docs/review-work-plan.md)
- [Ergonomics acceptance test](docs/ergonomics-acceptance.md)

Detailed work status, the decision log, and the exact next step are maintained in the second document so development can resume after an interruption without reconstructing prior work from memory.

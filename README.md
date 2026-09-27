# pdf-ocr-reviewer

A local desktop application for fast visual review of OCR layers across a larger number of PDF files. The interface runs through WebUI, the backend is written in Python, and PDFs are processed with PyMuPDF.

## Current status

A functional prototype is implemented:

- loading a folder and its PDF list;
- opening a document and progressively loading visible pages;
- side-by-side display of the scan and OCR layer;
- OCR layout, PDF order, and geometric order modes;
- OCR overlay;
- file statuses, problem pages, notes, and last position;
- atomically written `pdf-ocr-reviewer.manifest.json`;
- CSV export of review results;
- one-click OCR word marks and drag-to-mark regions, with autosaved notes;
- red/open, blue/repaired and green/confirmed regions, keyboard review and reopening;
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

## Targeted OCR repairs

Press **M** (or **Označovat**) to mark words with a click or regions with a drag.
Choose the problem type once; the application remembers it. Marks save immediately;
an optional note saves automatically. **Shift + drag** creates a region over an
existing mark. **Esc** returns to ordinary text selection. In Layout mode you can
also mark the spatial OCR pane.

The sidebar shows counts and a filterable list. **J/K** move between marks,
**N** focuses the selected mark's note, **C** confirms a repaired mark and advances
to the next repaired mark, and **R** reopens it. Red means open, blue means repaired
and awaiting your review, green means confirmed. Symbols and labels accompany the
colors. Reopening changes only the issue status, never the PDF. Cancel accidental
marks with the **× directly on the box**, in either reading or marking mode;
they remain recoverable in the **Zrušené** filter. **Špatná velikost boxu** covers
boxes that are too large or too small.

Everything is saved in `pdf-ocr-reviewer.manifest.json`. Existing version-1 manifests
are migrated on save. The first member, `repair_instructions`, describes the complete
repair contract, so a tool with access to the folder can receive this short prompt:

> Podle `pdf-ocr-reviewer.manifest.json` oprav otevřené připomínky u PDF od `XXX.pdf` po `YYY.pdf` včetně.

The reviewer does not run OCR or modify PDFs itself. After an external repair,
click **Načíst opravy** to reread both the manifest and the PDF. Close the reviewer
during a repair batch when possible; if its loaded manifest has changed externally,
it refuses to overwrite it. Unsaved issue drafts remain in the current session if
a save fails. A stale PDF anchor is visibly flagged and cannot be confirmed: mark
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

Detailed work status, the decision log, and the exact next step are maintained in the second document so development can resume after an interruption without reconstructing prior work from memory.

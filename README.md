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
- [Project structure](docs/project-structure.md)
- [Backend API](docs/backend-api.md)
- [Rendered page transport](docs/page-transport.md)
- [Implementation plan, tests, work status, and next steps](docs/implementation-plan.md)

Detailed work status, the decision log, and the exact next step are maintained in the second document so development can resume after an interruption without reconstructing prior work from memory.

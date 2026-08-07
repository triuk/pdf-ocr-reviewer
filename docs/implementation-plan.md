# Implementation plan and work status

## 8. Loading, virtualization, and memory

### Principles

- after opening a PDF, only page metadata is loaded first;
- the frontend creates empty blocks with the correct aspect ratio;
- the actual page is requested only when it is near the viewport;
- a limited number of pages above and below the current position are prefetched;
- distant image objects are released from memory;
- when zoom changes, only visible pages are rendered again;
- stale requests are ignored according to `requestId` and document generation.

### Default limits for the first version

- at most 8 image pages active in the frontend;
- access to the active PyMuPDF document is serialized by one reentrant lock;
- at most 2 waiting pages before and 2 after the viewport;
- a backend LRU cache is not implemented yet; the frontend keeps at most eight non-distant loaded pages unless more are visible at the same time;
- only one PyMuPDF document open in the render worker.

The limits will be adjusted only after measurements on real files.

---

## 9. Folder selection

The application supports three methods:

1. the **Open folder** button;
2. manually entering a path in the field;
3. a startup argument:

```bash
python main.py --folder "D:\\PDF\\OCR"
```

### Why a web-frontend dialog will not be the primary solution

The frontend can open a directory dialog using `window.showDirectoryPicker()` or an `<input type="file" webkitdirectory>` element. These mechanisms, however, return web objects such as `FileSystemDirectoryHandle` or `File` and relative names. For security reasons, they do not expose the absolute path of the selected folder to the Python backend.

In theory, the frontend could load all PDFs as binary data and send them to the backend. With many or large PDFs, however, that would unnecessarily copy entire files between the browser and Python, complicate repeated loading, and prevent the backend from directly writing the manifest into the selected folder. This mode is therefore not part of the design.

### Native backend dialog

The `selectFolderB()` function opens a dialog in the backend and returns the actual path. The implementation is isolated in `folder_dialog.py`, so it is not tightly coupled to a specific library.

The first version uses `tkinter.filedialog.askdirectory()` because it returns the path as a string and Python documents it as a dialog with native appearance. If testing on the target platform reveals a problem with Tk availability or dialog appearance, the implementation can be replaced by a platform-specific dialog without changing the API or the rest of the application.

The manual path and the `--folder` argument always remain functional fallbacks.

Technical references for this decision:

- [MDN: `showDirectoryPicker()`](https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker) – returns `FileSystemDirectoryHandle`, requires user activation, and does not have full support across all common browsers;
- [MDN: `FileSystemHandle`](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle) – public handle properties are `name` and `kind`, not an absolute system path;
- [MDN: `webkitdirectory`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory) – exposes selected files and relative paths inside the selected folder;
- [Python: `tkinter.filedialog.askdirectory()`](https://docs.python.org/3/library/dialog.html#tkinter.filedialog.askdirectory) – returns the path to the selected folder as a string.

Default scanning only covers the directly selected folder. Recursive traversal of subfolders is not part of the first version so relative names and the manifest remain unambiguous. It can be added later as an option.

---

## 10. JSON manifest

File name:

```text
pdf-ocr-reviewer.manifest.json
```

### Proposed schema version 1

```json
{
  "schema_version": 1,
  "application": "pdf-ocr-reviewer",
  "updated_at": "2026-08-04T12:00:00+02:00",
  "ui": {
    "last_file": "newsletter-1993-02.pdf",
    "zoom_percent": 100,
    "ocr_mode": "layout",
    "overlay": false,
    "status_filter": "all",
    "name_filter": "",
    "auto_advance": true
  },
  "files": {
    "newsletter-1993-02.pdf": {
      "identity": {
        "size": 21983210,
        "mtime_ns": 1785824750123456789
      },
      "status": "error",
      "last_page": 3,
      "problem_pages": [3, 6],
      "note": "Page 4 has incorrect column order.",
      "reviewed_at": "2026-08-04T12:15:00+02:00"
    }
  }
}
```

### Manifest rules

- the file key is the relative name with respect to the selected folder;
- page numbers are stored in the manifest as zero-based indexes, while the UI displays them starting at one;
- `size` and `mtime_ns` are used to detect PDF changes;
- OCR text, previews, and coordinates are not stored in the manifest;
- unknown manifest entries must not be silently discarded during loading;
- an invalid status or schema produces a visible error rather than a silent reset;
- a new schema version must have an explicit migration function.

### Writing

When the state changes, use this procedure:

1. serialize the entire manifest into a temporary file in the same folder;
2. finish writing and synchronizing the file;
3. replace the previous manifest;
4. on error, leave the original manifest unchanged;
5. display an error in the UI if the state cannot be saved.

The manifest is written after changing the status, problem pages, or note. Scroll position may be saved with a delay so the file is not rewritten for every pixel of movement.

### Changed and missing files

- a new PDF gets the `unreviewed` status;
- a changed file keeps its old record, but the UI marks it as `changed_since_review`;
- a file listed in the manifest but missing from the folder is shown only in a dedicated “missing” filter;
- automatic matching of renamed files by hashes is not part of the first version.

---

## 11. Security and data integrity

- the application must not write to PDFs;
- all frontend requests use an internal `fileId`, not an arbitrary path;
- the backend verifies that the requested file comes from the current catalog;
- OCR text is inserted into the DOM through `textContent`, not as HTML;
- page index and zoom are validated in the backend;
- the manifest is the only persistent file created in the selected folder;
- temporary previews are not stored beside PDFs;
- the first version assumes only one running process for one folder;
- if the folder is not writable, viewing may continue in read-only mode, but the UI must continuously indicate that results are not being saved.

---

## 12. Error states the UI must distinguish

- folder does not exist;
- folder cannot be read;
- manifest cannot be read;
- manifest contains invalid JSON;
- manifest has an unsupported version;
- manifest cannot be written;
- PDF cannot be opened;
- PDF is encrypted or requires a password;
- page cannot be rendered;
- OCR layer is empty;
- WebUI connection was interrupted;
- render request is stale after switching documents.

An error in one PDF must not terminate the application or prevent another file from being opened.

---

## 13. Testing

### Automated tests

1. **Manifest**
   - new manifest;
   - loading a valid manifest;
   - rejecting invalid JSON;
   - schema migration;
   - preserving unknown entries;
   - safe writing with a simulated error;
   - detecting file changes.

2. **Folder scanning**
   - only `.pdf`, regardless of extension letter case;
   - stable name sorting;
   - ignoring the manifest and other files;
   - behavior when a file disappears during scanning.

3. **PDF service**
   - page count and dimensions;
   - rotated pages;
   - page without text;
   - `words` and `rawdict` extraction;
   - invalid page index;
   - damaged or encrypted PDF.

4. **Binary packet**
   - correct header length;
   - Unicode in JSON;
   - empty OCR;
   - damaged packet;
   - large page.

### Manual acceptance tests

- rapid switching among at least 100 PDFs in the left list;
- smooth scrolling through a document with at least 100 pages;
- correct scan/OCR alignment for pages with different dimensions;
- restoration of the last file and page after restart;
- light and dark mode;
- keyboard-only operation;
- PDF changed after review;
- disconnecting and reconnecting the UI;
- folder without write permission;
- invalid manifest without loss of original data.

---

## 14. Measurable completion conditions for the first version

The first version is complete when:

- [ ] a folder can be opened and all of its PDFs displayed;
- [ ] files can be switched in the left column without restarting the application;
- [ ] pages of the selected PDF are displayed vertically;
- [ ] each page has an aligned OCR panel;
- [ ] Layout, PDF order, and Geometric order modes work;
- [ ] lazy loading works and distant pages do not all remain in memory;
- [ ] zoom and overlay work;
- [ ] file status and problem pages can be marked;
- [ ] a note can be added;
- [ ] state is saved to the manifest and restored after restart;
- [ ] a changed PDF is visibly marked;
- [ ] an unreadable file does not terminate the application;
- [x] automated manifest and binary-packet tests pass;
- [x] README matches the actual implementation and contains the current work status.

---

## 15. Work phases

### Phase 0 – design approval

- [x] approve this README;
- [x] adjust the scope of the first version if needed;
- [x] confirm the application name `pdf-ocr-reviewer`.

**Output:** approved plan without implementation changes.

### Phase 1 – skeleton and technical prototype

- [x] create the project structure;
- [x] adopt the WebUI lifecycle and functional control patterns from the example;
- [x] add pinned dependency versions;
- [x] open a PDF from the selected or entered folder;
- [x] obtain first-page metadata;
- [x] send one PNG preview through `send_raw()`;
- [x] display OCR objects in the right panel;
- [x] measure time, packet size, and memory consumption;
- [ ] decide on the final image transport after a real WebUI test.

**Output:** one PDF page visible beside its OCR layer.

### Phase 2 – folder and file list

- [x] implement the `--folder` argument;
- [x] implement manual path entry;
- [x] implement `tkinter.filedialog.askdirectory()` behind the `folder_dialog.py` interface;
- [x] scan PDFs;
- [x] create a stable `fileId`;
- [x] display the list and document switching;
- [x] handle invalid PDFs.

**Output:** fully functional left panel.

### Phase 3 – pages, lazy loading, and scroll

- [x] load metadata for all pages of the selected PDF;
- [x] create placeholders;
- [x] implement viewport tracking;
- [ ] replace the serialized callback with a real render queue;
- [x] cancel or ignore stale requests;
- [x] release Blob URLs;
- [ ] verify a long document.

**Output:** smooth scrolling without loading the entire document into memory.

### Phase 4 – OCR diagnostics

- [x] Layout mode;
- [x] PDF order mode;
- [x] Geometric order mode;
- [x] OCR overlay;
- [x] optional word or character boxes;
- [x] empty OCR layer as a visible state.

**Output:** all planned OCR review modes.

### Phase 5 – manifest and review workflow

- [x] manifest model;
- [x] loading and validation;
- [x] safe writing;
- [x] file statuses;
- [x] problem pages;
- [x] notes;
- [x] last position;
- [x] PDF change detection;
- [x] automatic advancement to the next file.

**Output:** a review can be interrupted and resumed at any time.

### Phase 6 – UI completion

- [x] filters;
- [x] status counts;
- [x] zoom slider;
- [x] overlay switch;
- [x] light and dark mode;
- [x] keyboard shortcuts;
- [x] error and status messages;
- [x] CSV export.

**Output:** usable first version.

### Phase 7 – tests and distribution

- [x] automated tests (10 tests);
- [ ] test on a real folder with a larger number of PDFs;
- [x] basic synthetic measurement of one packet;
- [ ] Windows test;
- [ ] Linux test;
- [ ] decide on a packaging method;
- [x] installation and startup instructions.

**Output:** reproducibly runnable version.

---

## 16. Outside the scope of the first version

- direct OCR layer corrections;
- saving changes into PDFs;
- OCR recognition of new documents;
- comparison of two PDF versions;
- automatic linguistic evaluation of OCR correctness;
- per-word annotations;
- multiple simultaneously connected clients;
- network or cloud mode;
- recursive traversal of subfolders;
- automatic matching of renamed PDFs by full hash;
- plugin system.

These features can be added only after the basic review workflow has been verified.

---

## 17. Rules for continuing unfinished work

After each completed unit of work, this README must be updated:

1. check off tasks that are actually complete;
2. update the **Current work status** section;
3. state the exact next step;
4. record important technical decisions in the **Decision log**;
5. record known bugs or unverified areas;
6. do not treat an experiment as a completed feature without a test;
7. when architecture changes, update the plan before the code.

### Current work status

```text
Phase: 3 – integration and manual verification
Completed: project skeleton, PDF backend, folder scan, manifest, binary packet, WebUI UI, OCR modes, lazy loading prototype, CSV export, read-only viewing fallback, 10 automated tests
In progress: verification of the actual WebUI browser transport and native folder dialog
Next action: install webui2 in a normal environment and run a smoke test with a real OCR PDF
Blocking issue: webui2 is not available in the restricted package index used during this implementation session
Known limitation: rendering is serialized inside callbacks; render_worker.py is not implemented yet
Known limitation: platform acceptance tests and the asynchronous render worker are not implemented
Last verified reference commit: 538123e061622a702709a1dd9c5a22cd32592dd3
Last verified UI commit: 72070fe146df89d3e0a6325a0475783bfda6d40d
```

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-04 | Use WebUI instead of PySide6 | The user selected WebUI and supplied a reference project |
| 2026-08-04 | Use a JSON manifest instead of SQLite | The state is small and local |
| 2026-08-04 | One shared scroll for scan and OCR | Guarantees permanent vertical alignment |
| 2026-08-04 | Adopt control and synchronization patterns from the supplied example | Provides a consistent, verified project foundation |
| 2026-08-04 | Do not use the frontend as a Git submodule | The UI will be specific to `pdf-ocr-reviewer` |
| 2026-08-04 | The first version only reads PDFs | Separates review from later corrections |
| 2026-08-04 | The project name is `pdf-ocr-reviewer` | Accurately describes the purpose and works for both repository and package |
| 2026-08-04 | Use only manually maintained CSS, without SCSS | A CSS build is unnecessary for the UI scope |
| 2026-08-04 | Do not add a separate `--server` mode | The application is intended as a local single-user GUI |
| 2026-08-04 | Handle folder selection with a backend dialog | The web API does not pass an absolute path to Python; the first implementation uses `tkinter.filedialog.askdirectory()` |
| 2026-08-04 | Page transport uses a 4-byte JSON header length, JSON, then a PNG payload | The format can be split unambiguously in both Python and JavaScript |
| 2026-08-04 | Serialize access to the active PyMuPDF document using `threading.RLock` | WebUI may handle callbacks concurrently; one document must not be processed concurrently |
| 2026-08-04 | The frontend keeps at most eight non-distant loaded pages | Lazy loading alone does not release pages the user has already passed |

### Work log

| Date | Work performed | Result |
|---|---|---|
| 2026-08-04 | Inspected the supplied ZIP, main Python backend, HTML, JavaScript, CSS, and Git metadata | Identified elements reusable for `pdf-ocr-reviewer` |
| 2026-08-04 | Created the implementation plan | Awaiting user approval |
| 2026-08-04 | Adjusted the plan: name, plain CSS, removal of server mode, and backend dialog choice | README matches the current decisions |
| 2026-08-04 | Created project structure, backend API, manifest, folder scanner, PDF service, and binary packet | Backend can be tested without running WebUI |
| 2026-08-04 | Created the WebUI frontend with PDF list, shared scroll, OCR modes, overlay, zoom, filters, and keyboard controls | Implementation is ready for a manual smoke test |
| 2026-08-04 | Added PyMuPDF serialization and release of distant Blob URLs | Removed two risks: concurrency and memory growth |
| 2026-08-04 | Ran `pytest -q` and syntax checks for Python and JavaScript | 10 tests passed; `node --check ui/index.js` passed |
| 2026-08-04 | Synthetic page at 1200 px / 405 words: render and packet assembly | 130.171 ms; packet 424,251 B; PNG 366,923 B; JSON 57,324 B; tracemalloc peak 1,219,660 B |
| 2026-08-04 | Added CSV export and fallback when manifest writing fails | PDF can still be opened and rendered; the save error is passed to the UI |

---

## 18. Known unverified parts of the prototype

- `webui2` could not be installed in this work environment because the restricted package index did not provide the package. The backend and frontend therefore passed automated and syntax tests, but actual window opening and transport through `send_raw` had not yet been manually verified.
- `render_worker.py` is intentionally only a reserved module for now. Rendering runs synchronously in the callback and is serialized by a lock.
- Viewing when manifest writing fails is covered by an automated test with a simulated error; an actually non-writable folder on the target system had not yet been tested manually.
- Layout displays OCR word-by-word from `get_text("words")`; character-level mode from `rawdict` has not yet been added.
- Acceptance tests on Windows, Linux, or a long real document had not yet been performed.

---

## 19. Originally approved scope

Approval of this plan confirms in particular:

- WebUI + Python + PyMuPDF;
- vanilla JavaScript and manually maintained CSS without SCSS;
- `pdf-ocr-reviewer.manifest.json` without SQLite;
- one shared scroll for the center and right columns;
- the first version only reviews PDFs and does not modify them;
- three OCR modes and an optional overlay;
- lazy loading of visible pages;
- file status, problem pages, note, and position restoration;
- backend folder selection with the first implementation using `tkinter.filedialog.askdirectory()`;
- no separate `--server` mode;
- a technical prototype transporting one page through `send_raw()` as the first implementation step;
- recursive folders, OCR editing, and automatic corrections only outside the first version.

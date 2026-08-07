# Architecture and design

## 1. Application goal

The application loads a folder with PDFs and provides a workspace with three columns:

1. a list of PDF files on the left;
2. image previews of all pages of the selected PDF stacked vertically in the center;
3. a corresponding visualization of each page's OCR layer on the right.

The user switches files in the left list and continuously scrolls through their pages. The center and right columns must remain exactly vertically aligned so the scan can be compared with OCR without searching for the corresponding position.

The first version of the application will not repair or otherwise modify PDFs. It is intended only for review, marking problem files and pages, and saving review results.

---

## 2. Approved and proposed technical decisions

| Area | Decision |
|---|---|
| Application type | Local desktop application with a web interface |
| GUI | WebUI / Python package `webui2` |
| Backend | Python |
| Frontend | HTML, CSS, and vanilla JavaScript without React or Vue |
| PDF handling | PyMuPDF |
| Persistent state | `pdf-ocr-reviewer.manifest.json` in the selected folder |
| Database | SQLite is not used in the first version |
| PDF modifications | Forbidden; source PDFs are opened read-only |
| Base mode | One local application and one client |
| Scrolling | One shared vertical scroll for scan and OCR |
| Page loading | Only visible and nearby pages, not the whole document at once |
| Default image format | PNG; change only if measurements justify it |

### Installation and startup

```bash
python -m venv .venv
# Activate the virtual environment for your operating system.
pip install -r requirements.txt
python main.py
```

Open a specific folder at startup:

```bash
python main.py --folder "D:\\PDF\\OCR"
```

Automated tests:

```bash
pytest -q
```

Benchmark one real page without WebUI transport:

```bash
python tools/benchmark_page.py "D:\\PDF\\OCR\\file.pdf" --page 1 --width 1200
```

### Why SQL is not needed

A JSON manifest is sufficient for:

- review status of individual files;
- the list of problem pages;
- a note for each file;
- the last opened file and page;
- display settings;
- detecting that a PDF has changed since the last review.

SQLite would only be considered when storing large numbers of per-word annotations, change history, concurrent work by multiple processes, or complex queries over the data.

---

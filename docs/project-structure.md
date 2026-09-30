# Backend and transport

## 5. Proposed project structure

```text
pdf-ocr-reviewer/
├── README.md
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── app/
│   ├── __init__.py
│   ├── application.py
│   ├── api.py
│   ├── models.py
│   ├── folder_dialog.py
│   ├── folder_scanner.py
│   ├── manifest.py
│   ├── review.py
│   ├── pdf_document.py
│   ├── render_worker.py
│   └── raw_packet.py
├── ui/
│   ├── favicon.svg
│   ├── index.html
│   ├── state.js
│   ├── files.js
│   ├── document.js
│   ├── pages.js
│   ├── scan-zoom.js
│   ├── issues.js
│   ├── workflow.js
│   └── index.css
├── tools/
│   ├── benchmark_page.py
│   └── smoke_region_review.py
├── tests/
│   ├── test_manifest.py
│   ├── test_region_review.py
│   ├── test_folder_scanner.py
│   ├── test_raw_packet.py
│   └── test_pdf_document.py
└── samples/
    └── README.md
```

### Module responsibilities

- `main.py` – argument processing and application startup only;
- `application.py` – WebUI window, lifecycle, and component assembly;
- `api.py` – all functions bound through `window.bind()`;
- `models.py` – data models and validation constants;
- `folder_dialog.py` – folder selection and its fallback solution;
- `folder_scanner.py` – safe PDF listing and file identities;
- `manifest.py` – JSON loading, migration, validation, and safe writing;
- `review.py` – repair instructions, issue validation, hashes and companion file discovery;
- `ui/issues.js` – marking, issue overlays, autosave, review navigation and status actions;
- `ui/scan-zoom.js` – cursor-anchored image zoom, pan and debounced raster refresh;
- `pdf_document.py` – PDF metadata and OCR extraction;
- `render_worker.py` – render request queue;
- `raw_packet.py` – packing and unpacking binary messages for the frontend.

---

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
│   ├── pdf_document.py
│   ├── render_worker.py
│   └── raw_packet.py
├── ui/
│   ├── favicon.ico
│   ├── index.html
│   ├── index.js
│   └── index.css
├── tools/
│   └── benchmark_page.py
├── tests/
│   ├── test_manifest.py
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
- `pdf_document.py` – PDF metadata and OCR extraction;
- `render_worker.py` – render request queue;
- `raw_packet.py` – packing and unpacking binary messages for the frontend.

---

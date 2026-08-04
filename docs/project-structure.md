# Backend a transport

## 5. Navržená struktura projektu

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

### Odpovědnosti modulů

- `main.py` – pouze zpracování argumentů a spuštění aplikace;
- `application.py` – WebUI okno, lifecycle a sestavení komponent;
- `api.py` – všechny funkce navázané pomocí `window.bind()`;
- `models.py` – datové modely a validační konstanty;
- `folder_dialog.py` – výběr složky a jeho náhradní řešení;
- `folder_scanner.py` – bezpečný seznam PDF a jejich identity;
- `manifest.py` – načtení, migrace, validace a bezpečný zápis JSON;
- `pdf_document.py` – metadata PDF a extrakce OCR;
- `render_worker.py` – fronta požadavků na vykreslení;
- `raw_packet.py` – balení a rozbalení binárních zpráv pro frontend.

---

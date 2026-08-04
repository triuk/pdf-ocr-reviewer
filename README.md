# pdf-ocr-reviewer

Lokální desktopová aplikace pro rychlou vizuální kontrolu OCR vrstev ve větším množství PDF. Rozhraní běží přes WebUI, backend je v Pythonu a PDF zpracovává PyMuPDF.

## Aktuální stav

Je implementován první funkční prototyp:

- načtení složky a seznamu PDF;
- otevření dokumentu a průběžné načítání viditelných stran;
- společné zobrazení skenu a OCR vrstvy;
- režimy OCR rozložení, pořadí v PDF a geometrické pořadí;
- OCR overlay;
- stavy souborů, problematické stránky, poznámky a poslední pozice;
- atomicky zapisovaný `pdf-ocr-reviewer.manifest.json`;
- export výsledků do CSV;
- automatické backendové testy.

Skutečný běh WebUI musí být ještě ověřen v prostředí s dostupným balíčkem `webui2`.

## Instalace

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

Volitelné otevření složky při startu:

```bash
python main.py --folder "/path/to/pdf-folder"
```

Testy:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

## Dokumentace a pokračování práce

- [Cíl, technická rozhodnutí a spuštění](docs/product-overview.md)
- [WebUI reference a převzaté vzory](docs/webui-reference.md)
- [Přehled uživatelského rozhraní](docs/ui-overview.md)
- [Levý sloupec a společný scroll](docs/ui-columns-and-scroll.md)
- [OCR režimy a klávesové ovládání](docs/ui-ocr-and-controls.md)
- [Struktura projektu](docs/project-structure.md)
- [Backend API](docs/backend-api.md)
- [Transport vykreslených stran](docs/page-transport.md)
- [Implementační plán, testy, pracovní stav a další kroky](docs/implementation-plan.md)

Podrobný pracovní stav, decision log a přesný následující krok jsou vedeny v druhém dokumentu, aby bylo možné po přerušení navázat bez domýšlení předchozí práce.

# pdf-ocr-reviewer

Lokální desktopová aplikace pro rychlou vizuální kontrolu OCR vrstev ve větším množství PDF. Rozhraní běží přes WebUI, backend je v Pythonu a PDF zpracovává PyMuPDF.

## Aktuální stav

Je implementován funkční prototyp:

- načtení složky a seznamu PDF;
- otevření dokumentu a průběžné načítání viditelných stran;
- společné zobrazení skenu a OCR vrstvy;
- režimy OCR rozložení, pořadí v PDF a geometrické pořadí;
- OCR overlay;
- stavy souborů, problematické stránky, poznámky a poslední pozice;
- atomicky zapisovaný `pdf-ocr-reviewer.manifest.json`;
- export výsledků do CSV;
- automatické backendové testy;
- automatické one-file buildy pro Linux x86_64 a Windows x86_64 přes GitHub Actions.

## Hotová binárka

Každý push na `main` spustí testy a vytvoří dva samostatné one-file artefakty v GitHub Actions:

- `pdf-ocr-reviewer-linux-x86_64`
- `pdf-ocr-reviewer-windows-x86_64.exe`

Linuxová binárka po stažení potřebuje pouze nastavit příznak spuštění:

```bash
chmod +x pdf-ocr-reviewer-linux-x86_64
./pdf-ocr-reviewer-linux-x86_64
```

Linuxový one-file build před spuštěním systémového prohlížeče dočasně obnoví původní `LD_LIBRARY_PATH` uložený PyInstallerem v `LD_LIBRARY_PATH_ORIG`. Tím systémový Firefox/Chromium nenačítá nekompatibilní sdílené knihovny z dočasného adresáře one-file balíčku. Po spuštění prohlížeče aplikace obnoví vlastní PyInstaller prostředí.

Při vytvoření tagu `v*`, například `v0.1.0`, stejný workflow po úspěšném testu a buildu automaticky vytvoří GitHub Release. Release obsahuje obě one-file binárky a `SHA256SUMS.txt`.

Každá sestavená binárka před publikováním projde vlastním:

```bash
pdf-ocr-reviewer --self-test
```

Self-test ověřuje import PyMuPDF a WebUI, Tk/Tcl runtime, přítomnost zabalených UI souborů a skutečné vytvoření, otevření a vykreslení testovacího PDF.

## Spuštění ze zdrojového kódu

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

Volitelné otevření složky při startu:

```bash
python main.py --folder "/path/to/pdf-folder"
```

Self-test zdrojové instalace:

```bash
python main.py --self-test
```

Testy:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

## Lokální one-file build

```bash
python -m pip install -r requirements-build.txt
pyinstaller --noconfirm --clean pdf-ocr-reviewer.spec
```

Výsledek vznikne jako `dist/pdf-ocr-reviewer` na Linuxu nebo `dist/pdf-ocr-reviewer.exe` na Windows.

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

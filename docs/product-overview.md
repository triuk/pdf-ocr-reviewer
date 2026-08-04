# Architektura a návrh

## 1. Cíl aplikace

Aplikace načte složku s PDF a nabídne pracovní plochu se třemi sloupci:

1. vlevo seznam PDF souborů;
2. uprostřed obrazové náhledy všech stran vybraného PDF pod sebou;
3. vpravo odpovídající vizualizaci OCR vrstvy jednotlivých stran.

Uživatel bude přepínat soubory v levém seznamu a souvisle rolovat jejich stránky. Prostřední a pravý sloupec musí zůstat přesně vertikálně zarovnané, aby bylo možné bez hledání porovnávat sken s OCR.

Aplikace v první verzi nebude PDF opravovat ani jinak měnit. Bude sloužit pouze ke kontrole, označování problematických souborů a stran a ukládání výsledků kontroly.

---

## 2. Schválená a navržená technická rozhodnutí

| Oblast | Rozhodnutí |
|---|---|
| Typ aplikace | Lokální desktopová aplikace s webovým rozhraním |
| GUI | WebUI / Python balíček `webui2` |
| Backend | Python |
| Frontend | HTML, CSS a čistý JavaScript bez Reactu nebo Vue |
| Práce s PDF | PyMuPDF |
| Trvalý stav | `pdf-ocr-reviewer.manifest.json` ve zvolené složce |
| Databáze | SQLite se v první verzi nepoužije |
| Úpravy PDF | Zakázány; zdrojové PDF se otevírá pouze pro čtení |
| Základní režim | Jedna lokální aplikace a jeden klient |
| Způsob rolování | Jeden společný svislý scroll pro sken i OCR |
| Načítání stran | Pouze viditelné a blízké stránky, ne celý dokument najednou |
| Výchozí obrazový formát | PNG; případná změna až podle měření |

### Instalace a spuštění

```bash
python -m venv .venv
# Aktivujte virtuální prostředí podle používaného systému.
pip install -r requirements.txt
python main.py
```

Otevření konkrétní složky při startu:

```bash
python main.py --folder "D:\\PDF\\OCR"
```

Automatické testy:

```bash
pytest -q
```

Benchmark jedné skutečné strany bez WebUI transportu:

```bash
python tools/benchmark_page.py "D:\\PDF\\OCR\\soubor.pdf" --page 1 --width 1200
```

### Proč není potřeba SQL

Manifest JSON postačuje pro:

- stav kontroly jednotlivých souborů;
- seznam problematických stran;
- poznámku k souboru;
- poslední otevřený soubor a stránku;
- nastavení zobrazení;
- rozpoznání, že se PDF od poslední kontroly změnilo.

SQLite by se zvažovalo až při ukládání velkého množství anotací jednotlivých slov, historie změn, souběžné práci více procesů nebo složitých dotazech nad daty.

---

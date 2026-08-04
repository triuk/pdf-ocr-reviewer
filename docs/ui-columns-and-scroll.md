# Levý sloupec a společný scroll

### 4.2 Levý sloupec

Každý soubor zobrazí:

- stav kontroly;
- název;
- počet stran po načtení metadat;
- označení, že se soubor od poslední kontroly změnil;
- počet označených problematických stran.

Stavy:

- `unreviewed` – nezkontrolováno;
- `ok` – v pořádku;
- `error` – nalezena chyba OCR;
- `needs_review` – vyžaduje další kontrolu.

Nad seznamem bude:

- textový filtr názvu;
- filtr podle stavu;
- souhrn počtů souborů v jednotlivých stavech.

### 4.3 Prostřední a pravý sloupec

Oba sloupce budou součástí jednoho společného scrollovacího kontejneru. Každá stránka vytvoří jeden řádek CSS gridu:

```text
page-row
├── scan-pane
└── ocr-pane
```

Tím se vyloučí postupné rozjíždění dvou nezávislých scrollbarů.

Každý řádek bude mít:

- číslo stránky;
- tlačítko pro označení problematické stránky;
- obraz stránky vlevo;
- OCR zobrazení vpravo;
- stejné rozměry obou ploch;
- zachovaný poměr stran konkrétní stránky.

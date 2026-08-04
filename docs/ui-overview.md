# Návrh uživatelského rozhraní

## 4. Návrh uživatelského rozhraní

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Otevřít složku | cesta | režim OCR | overlay | zoom | stav kontroly        │
├──────────────────┬──────────────────────────┬───────────────────────────────┤
│ PDF soubory      │ Sken                     │ OCR vrstva                    │
│                  │                          │                               │
│ ○ soubor-01.pdf  │ ┌──────────────────────┐ │ ┌───────────────────────────┐ │
│ ✓ soubor-02.pdf  │ │ strana 1             │ │ │ OCR strany 1              │ │
│ ! soubor-03.pdf  │ └──────────────────────┘ │ └───────────────────────────┘ │
│ ? soubor-04.pdf  │                          │                               │
│                  │ ┌──────────────────────┐ │ ┌───────────────────────────┐ │
│ Filtr            │ │ strana 2             │ │ │ OCR strany 2              │ │
│ Stav             │ └──────────────────────┘ │ └───────────────────────────┘ │
└──────────────────┴──────────────────────────┴───────────────────────────────┘
```

### 4.1 Horní lišta

- tlačítko **Otevřít složku**;
- zobrazení aktuální cesty;
- přepínač režimu OCR;
- switch pro OCR overlay nad skenem;
- slider zoomu;
- tlačítka nebo klávesové akce pro stav souboru;
- indikátor neuložených změn a případné chyby manifestu.

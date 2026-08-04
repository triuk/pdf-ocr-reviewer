# Backend API a transport stránek

## 6. Backend API mezi JavaScriptem a Pythonem

Názvy končí:

- `B` pro funkce implementované v backendu;
- `F` pro funkce implementované ve frontendu.

Tento vzor je převzat z referenčního projektu.

### Navržené backend funkce

| Funkce | Účel |
|---|---|
| `syncStateB()` | vrátí celý aktuální stav potřebný po připojení UI |
| `selectFolderB()` | otevře lokální dialog pro výběr složky |
| `openFolderB(path)` | ověří cestu, načte manifest a proskenuje PDF |
| `refreshFolderB()` | znovu proskenuje aktuální složku |
| `openDocumentB(fileId)` | otevře PDF a vrátí metadata stran |
| `requestPageB(requestId, fileId, pageIndex, renderWidth, ocrMode)` | zařadí vykreslení stránky do fronty |
| `setFileStatusB(fileId, status)` | nastaví stav kontroly |
| `setLastPageB(fileId, pageIndex)` | uloží poslední pozici |
| `toggleProblemPageB(fileId, pageIndex)` | přidá nebo odebere problematickou stránku |
| `setFileNoteB(fileId, note)` | uloží poznámku |
| `setUiOptionsB(optionsJson)` | uloží zoom, OCR režim, overlay a filtry |
| `exportCsvB()` | vytvoří CSV souhrn výsledků kontroly |

### Formát běžných odpovědí

Malé odpovědi se budou vracet jako JSON řetězec v jednotném obalu:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Při chybě:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "PDF_OPEN_FAILED",
    "message": "Soubor nelze otevřít."
  }
}
```

Frontend nebude rozhodovat podle textu chyby, ale podle stabilního `code`.

---

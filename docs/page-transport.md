# Transport vykreslených stran

## 7. Přenos vykreslených stran

Dodaný příklad ověřuje přenos binárních dat z Pythonu do JavaScriptu pomocí `send_raw()`. Stejný princip použijeme pro stránky PDF.

### Navržený postup

1. Frontend vytvoří `requestId`.
2. Zavolá `requestPageB(...)`.
3. Backend vloží požadavek do jediné renderovací fronty.
4. Prototyp požadavek serializuje zámkem, vykreslí PNG a extrahuje OCR data ve WebUI callbacku.
5. Python odešle jeden binární paket do frontend funkce `pageReadyF(rawData)`.
6. JavaScript vytvoří z obrazových bytů `Blob URL` a doplní OCR panel.
7. Staré Blob URL se při odložení stránky zruší.

### Předběžný formát paketu

```text
4 bytes      délka JSON hlavičky, little endian
N bytes      JSON hlavička v UTF-8
remaining    PNG data
```

Hlavička:

```json
{
  "request_id": "...",
  "file_id": "...",
  "page_index": 0,
  "width": 1240,
  "height": 1754,
  "mime": "image/png",
  "ocr": {
    "mode": "layout",
    "items": []
  }
}
```

### Technická ověřovací brána

Hned v prvním prototypu se změří:

- spolehlivost přenosu větší PNG stránky přes `send_raw()`;
- rychlost přenosu;
- paměť v Pythonu a prohlížeči;
- chování při rychlém přechodu mezi soubory.

Pokud bude jeden kombinovaný paket příliš velký nebo nepraktický, zachová se stejné API a vymění se pouze transportní vrstva za:

1. oddělený binární obraz a JSON metadata; nebo
2. dočasné lokální soubory obsluhované backendem.

Tato změna nesmí ovlivnit manifest ani zbytek UI.

---


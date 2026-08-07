# Rendered page transport

## 7. Transport of rendered pages

The supplied example verifies binary data transfer from Python to JavaScript using `send_raw()`. We will use the same principle for PDF pages.

### Proposed flow

1. The frontend creates a `requestId`.
2. It calls `requestPageB(...)`.
3. The backend places the request into a single render queue.
4. The prototype serializes the request with a lock, renders PNG, and extracts OCR data inside the WebUI callback.
5. Python sends one binary packet to the frontend function `pageReadyF(rawData)`.
6. JavaScript creates a `Blob URL` from the image bytes and fills the OCR panel.
7. Old Blob URLs are revoked when a page is unloaded.

### Preliminary packet format

```text
4 bytes      JSON header length, little endian
N bytes      UTF-8 JSON header
remaining    PNG data
```

Header:

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

### Technical validation gate

The first prototype will immediately measure:

- reliability of transferring a larger PNG page through `send_raw()`;
- transfer speed;
- memory use in Python and the browser;
- behavior during rapid switching between files.

If one combined packet is too large or impractical, the same API will be preserved and only the transport layer will be replaced by:

1. a separate binary image and JSON metadata; or
2. temporary local files served by the backend.

This change must not affect the manifest or the rest of the UI.

---


# Backend API and page transport

## 6. Backend API between JavaScript and Python

Names end with:

- `B` for functions implemented in the backend;
- `F` for functions implemented in the frontend.

This pattern is adopted from the reference project.

### Proposed backend functions

| Function | Purpose |
|---|---|
| `syncStateB()` | returns the complete current state needed after the UI connects |
| `selectFolderB()` | opens the local folder selection dialog |
| `openFolderB(path)` | validates the path, loads the manifest, and scans PDFs |
| `refreshFolderB()` | rescans the current folder |
| `openDocumentB(fileId)` | opens a PDF and returns page metadata |
| `requestPageB(requestId, fileId, pageIndex, renderWidth, ocrMode)` | queues a page render request |
| `setFileStatusB(fileId, status)` | sets the review status |
| `setLastPageB(fileId, pageIndex)` | saves the last position |
| `toggleProblemPageB(fileId, pageIndex)` | adds or removes a problem page |
| `setFileNoteB(fileId, note)` | saves a note |
| `setUiOptionsB(optionsJson)` | saves zoom, OCR mode, overlay, and filters |
| `exportCsvB()` | creates a CSV summary of review results |
| `addIssueB(fileId, payloadJson)` | saves a word/region issue with OCR snapshot and PDF version anchor |
| `updateIssueB(fileId, issueId, patchJson)` | autosaves type/note or confirms, reopens, cancels an issue |

`addIssueB` accepts `page_index`, `bbox`, `kind`, optional `note`, and
`expected_sha256` from `openDocumentB`. `updateIssueB` accepts `expected_sha256`
and any of `note`, `kind`, `status`. Both return `file_id`, `issue_id`, `issues`,
`issue_counts` and `ocr_sha256`. Each issue in responses also includes computed
`stale`; this transient flag is not written to the manifest.

`openDocumentB` includes the same issue data. File-list responses include status
counts for the regions. `refreshFolderB` rereads the manifest; the frontend then
reopens the active document to invalidate old renders and restore review position.
Every save checks that the manifest has not been replaced externally since load or
the previous successful write. A conflict returns a save error without overwriting
the newer file. See [the repair contract](region-review.md).

### Format of regular responses

Small responses are returned as a JSON string in a consistent envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

On error:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "PDF_OPEN_FAILED",
    "message": "The file cannot be opened."
  }
}
```

The frontend does not branch on the error text, but on the stable `code`.

---

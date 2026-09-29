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
| `setReviewCompleteB(fileId, payloadJson)` | sets independent whole-file inspection completion |
| `setFileStatusB(fileId, status)` | legacy classification API, retained for compatibility |
| `setLastPageB(fileId, pageIndex)` | saves the last position |
| `toggleProblemPageB(fileId, pageIndex)` | adds or removes a problem page |
| `setFileNoteB(fileId, note)` | saves a note |
| `setUiOptionsB(optionsJson)` | saves zoom, OCR mode, overlay, and filters |
| `exportCsvB()` | creates a CSV summary of review results |
| `addIssueB(fileId, payloadJson)` | saves a word/region issue with OCR snapshot and PDF version anchor |
| `updateIssueB(fileId, issueId, patchJson)` | autosaves type/note, deletes (`dismissed`) or restores (`open`) a mark; legacy `verified` remains compatible |

`setReviewCompleteB` accepts `{complete: boolean, expected_sha256: string}` and
returns the updated public file entry, including `review_complete`. It checks the
active document context, PDF hash and manifest revision. Completion changes leave
legacy classification and issue data unchanged. Open-document and file-list data
both include `review_complete`. CSV appends `review_complete` and `review_completed_at`.

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


## Request context and recovery (2026-09-29)

`syncStateB` returns `context_id` for the current folder session, and
`openDocumentB` returns `document_id` for the active PDF instance. All original
callbacks except `syncStateB` take one additional final JSON string argument:
`{"context_id":"...","document_id":"..."}`. Folder operations validate the
folder session; document-bound mutations and render requests also validate the
active document and requested file. A rejected request returns `STALE_CONTEXT`.
The frontend serializes navigation and ignores responses from superseded contexts.

Local recovery callbacks are independent of the currently selected document:

- `saveDraftB(draft_json)` journals a draft with folder, fileId, optional issueId,
  token, note, base_note, expected_sha256 and optional kind/base_kind/base_revision.
- `deleteDraftB(token)` acknowledges only that draft version.
- `listBackupsB(folder)` returns valid backup choices and the observed manifest revision.
- `restoreBackupB(folder, backup_id, expected_revision_json)` restores under the
  writer lock and returns the reopened folder state. The replaced bytes are retained.

Folder state includes recovered `drafts` and a possible `draft_error`; a broken
local recovery database is never silently replaced. Draft storage does not alter
the shared manifest. The manifest writer requires an explicit expected revision;
see `region-review.md` for the external CLI protocol.

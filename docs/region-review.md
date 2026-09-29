# Region review and repair manifest

Implemented 2026-09-25: extend the existing review workflow with persistent
word/region issues, without editing PDFs in the reviewer. Mark with one click or a
drag, reuse the last issue kind, save automatically, and review repairs with keyboard
navigation. Reopening an issue changes its review status only.

Schema 2 migrates schema 1 without losing file notes, page flags, UI state or unknown
fields. `repair_instructions` is the first JSON member and documents the external
repair contract. Each file has `issues`, its observed `ocr_sha256`, and relative
`resources` names for accompanying source/QA files. Each issue has a UUID, zero-based
page index, a review rectangle, page geometry, OCR target snapshots, original and
current target hashes, kind, note, status and append-only history.

Coordinates are PDF points relative to the upper-left corner of the **displayed,
cropped and rotated page**. In PyMuPDF, apply `page.derotation_matrix` to convert
them back for text operations. The rectangle identifies a review area, not an
instruction to delete every intersecting text object. Word indexes are extraction
snapshots, not stable object identifiers.

Statuses: `open` (red), `fixed` (blue, awaiting human review), `verified` (green),
`dismissed` (an accidental/cancelled mark, retained in history). Only the external
repairer produces `fixed`; the reviewer confirms or reopens it. No PDF rollback.

External writers must atomically replace the manifest, preserve unrelated data,
record repair results/hashes and keep other annotations anchored to the resulting
PDF only after verifying their targets did not change. Old QA PASS reports apply
only to their recorded hashes. The reviewer refuses to overwrite an externally
changed manifest. Reload reopens the PDF and restores the reading position.

Validation covers migration, invalid issue data, local/rotated coordinates, write
failures, external edits, status/history round trips and version mismatches. UI
checks cover click/drag marking, autosave, navigation, confirm/reopen and reload.

## Example issue

The following is illustrative; real hashes are computed from the PDF bytes.
`source_sha256` is immutable provenance, whereas `target_sha256` binds the current
region/targets to a PDF version. `text` and `targets` are OCR snapshots, not user
instructions. A repair must include `result` before setting status to `fixed`.
The historical key `oversized` now means **Špatná velikost boxu**, including both
oversized and undersized boxes. Existing marks keep their keys and histories.

```json
{
  "id": "88ffca6b-7418-4e43-b56e-41aa1abc6bcd",
  "page_index": 0,
  "bbox": [40, 60, 150, 85],
  "page_width": 600,
  "page_height": 850,
  "page_rotation": 0,
  "coordinate_system": "displayed_page_points_top_left",
  "text": "Nadpis",
  "targets": [{"x0": 40, "y0": 60, "x1": 150, "y1": 85, "text": "Nadpis", "block": 0, "line": 0, "word": 0}],
  "kind": "oversized",
  "note": "Text je správně, zmenšit box.",
  "status": "open",
  "source_sha256": "<64 lowercase hexadecimal characters>",
  "target_sha256": "<64 lowercase hexadecimal characters>",
  "created_at": "2026-09-25T20:00:00+02:00",
  "updated_at": "2026-09-25T20:00:00+02:00",
  "history": [{"at": "2026-09-25T20:00:00+02:00", "action": "created", "to": "open"}]
}
```

State transitions in the UI preserve the prior values and append history. A
cancelled accidental mark is retained as `dismissed`, with a restore action in its
filter. The **× directly on each box** cancels it without selecting it first or
scrolling to the footer. A reopened issue may have an earlier `result`: that result describes the
previous attempt, not a resolution of the new request.

The application hashes PDFs when opening them and checks the active hash before
saving issue changes. It detects stale targets, but does not guess their new
locations. Human confirmation of a stale target is blocked. Manifest replacement
detection is optimistic concurrency protection, not a multiwriter database lock;
avoid simultaneous writing by external tools and the reviewer.

## Cooperative writer protocol (instructions version 2)

Before reading the manifest, capture its revision with:

```bash
python main.py --folder /path/to/pdfs --manifest-revision
```

Keep that revision while preparing a separate candidate JSON. After verifying
PDF repairs, commit the candidate through the shared writer:

```bash
python main.py --folder /path/to/pdfs --write-manifest candidate.json --expected-revision HASH
```

Use `missing` only when the initial manifest did not exist. The Python interface
is `save_manifest(folder, candidate, expected_revision=revision)` (`None` for a
missing manifest). Both hold `.pdf-ocr-reviewer.manifest.json.lock` across the
revision check and replacement. Never delete that lock file. A conflict requires
reading and reconciling the new manifest, not merely substituting its hash.
Direct writes by unrelated programs do not participate in this protection.

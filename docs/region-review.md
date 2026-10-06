# Region review and repair manifest

Implemented 2026-09-25: extend the existing review workflow with persistent
word/region issues, without editing PDFs in the reviewer. Mark with one click or a
drag, reuse the last issue kind, save automatically, and browse marks with keyboard
navigation. The manifest is the control file for OCR passes performed outside
the application; the reviewer never runs the repair itself.

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

The current workflow uses two visible states: `open` (red, **K opravě**) and
`fixed` (blue, **Po opravě**). Both are retained requests for the next external
pass. A satisfactory result is removed with **× directly on the box**; an
unsatisfactory result is simply left in place, optionally with an updated note.
There is no V/C confirmation loop or R reopening step.

Removal stores `dismissed` and preserves history. **Archiv → Obnovit označení**
restores it to `open`, without changing the PDF. Legacy `verified` marks remain
archived and excluded; migration never silently queues previously accepted work.
The legacy backend confirmation operation remains compatible with older clients,
but the current UI does not offer it.

External writers must atomically replace the manifest, preserve unrelated data,
record repair results/hashes and keep other annotations anchored to the resulting
PDF only after verifying their targets did not change. Old QA PASS reports apply
only to their recorded hashes. The reviewer refuses to overwrite an externally
changed manifest. Reload reopens the PDF and restores the reading position.

Validation covers migration, invalid issue data, local/rotated coordinates, write
failures, external edits, status/history round trips and version mismatches. UI
checks cover click/drag marking, autosave, navigation, deletion/restoration and reload.

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

State transitions preserve prior values and append history. The **× directly on
each box** deletes it without selecting it first or scrolling to the footer.
Both the cross and **X** select the next retained mark in the current PDF/filter,
wrapping to the first remaining mark at the end. If none remain, selection clears.
A restored issue may have an earlier `result`: that describes the previous attempt.

The application hashes PDFs when opening them and checks the active hash before
saving issue changes. It detects stale targets, but does not guess their new
locations. Stale locations are flagged for fresh marking. Manifest replacement
uses an expected revision checked under the cooperative writer lock described
below. External writers must use the same helper to participate in that protection.

## External passes (instructions version 3)

`repair_instructions.workflow.eligible_statuses` is `["open", "fixed"]`;
`excluded_statuses` is `["dismissed", "verified"]`. The short prompt can remain:

> Podle `pdf-ocr-reviewer.manifest.json` oprav otevřené připomínky u PDF od `XXX.pdf` po `YYY.pdf` včetně.

Here “otevřené připomínky” means every retained red or blue mark. Select a snapshot
of eligible issues at the start of each explicitly requested pass; never requeue
`fixed` within that same pass. Subsequent passes include retained blue marks again.
On success, set `fixed`, store `result` and append a history record whose `from`
is the actual prior state, including `fixed` for repeat attempts. Before replacing
an earlier result, include it as `previous_result` in that new history record.
On failure set `open`, append `repair_blocked`, and retain prior results/history.
Concurrent deletion or changed notes must be reconciled before committing results.

Migration replaces exact built-in v1/v2 rules, including the old “only open” rule,
and preserves custom rules and unknown fields. It leaves issue states and history
unchanged. The schema remains version 2; the instructions are version 3.

## Cooperative writer protocol

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

## Recovery

Every successful manifest replacement keeps up to ten previous valid snapshots
in `.pdf-ocr-reviewer-backups`. **Další → Zálohy** lists them for the folder entered in the
path field, including when a damaged manifest cannot be opened. Restoration
checks the revision selected in that dialog and preserves the replaced bytes as
`.pdf-ocr-reviewer-backups/before-restore.json`. PDF bytes are not changed.

Note drafts are journaled separately in a local SQLite file before manifest
saving. On Linux the default is `$XDG_STATE_HOME/pdf-ocr-reviewer/drafts.sqlite3`
(or `~/.local/state/pdf-ocr-reviewer/drafts.sqlite3`); on Windows it is under
`%LOCALAPPDATA%/pdf-ocr-reviewer`. Tests can override the directory with
`PDF_OCR_REVIEWER_STATE_DIR`. This local recovery journal is not a repair input.

After reopening a document, **Obnovené poznámky** shows recovered text alongside
its current saved counterpart. **Použít koncept** explicitly applies it to the
visible revision; **Ponechat uložené** discards that local draft. Missing files or
issues keep their drafts available for copying. A successful old save only
acknowledges its own draft token and cannot erase newer typing.

## Browsing across files

The PDF filters combine name, inspection completion and issue state. **Má ponechané
připomínky** includes PDFs with red or blue marks; **Má místa po opravě** shows
PDFs with blue marks. Arrow navigation honors those filters; completion changes stay on the current PDF.
**J/K** browse marks in the current PDF without changing their status. **N** focuses
the note. **Obnovit** reloads externally saved PDF and manifest changes.

## Whole-file completion

**OK** beside each filename changes `review_complete`, which records a finished
inspection independently of issue status. It does not open or switch PDFs.
Checking it does not exclude retained `open`/`fixed` issues from external passes.
`review_completed_at` records its time. The UI does not overwrite legacy `status`
or `reviewed_at`; older `ok` entries default to checked and all other legacy states
default to unchecked. A stored explicit boolean always takes precedence.

`ui.review_filter` stores `all`, `unreviewed` or `reviewed`. Legacy `status_filter`
and `auto_advance` remain preserved but are not used by the simplified interface.
CSV keeps its original columns and appends completion and its timestamp.

## Version-bound acceptance of repairs

The compact **✓** button beside **OK** is separate from inspection completion.
Orange means the current PDF has not been accepted; green means it has. Its tooltip
explains the action. Open the PDF, finish inspection with OK and remove satisfactory
retained open/fixed marks with × before accepting. Clicking green revokes acceptance.
Neither action changes issues, notes or OK. No hash needs to be entered or sent in chat.

Acceptance is saved by the official manifest writer as optional schema-2
`file.repair_acceptance = {ocr_sha256, accepted_at}` with a timezone-aware timestamp.
`repair_acceptance_history` appends `{action: accepted|revoked, ocr_sha256, at}`.
Absent fields in older manifests mean no acceptance. Unknown fields are preserved.
The UI derives `repairs_accepted` from the receipt, current observed PDF hash,
unchanged file identity, completed inspection and absence of retained open/fixed marks.
On PDF replacement, the old receipt/history remain evidence for the old bytes;
they cannot accept a different hash. External writers must preserve them, never
create human acceptance. The backend rechecks actual bytes and document/folder
context on click, and rejects stale PDFs or manifest revisions without overwriting
newer work. CSV appends acceptance, time and the receipt hash.

This records a human decision about the current PDF; archive acceptance still
requires the external workflow's remaining quality and manifest checks.

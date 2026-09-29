# OCR modes and keyboard controls

### 4.4 OCR modes

The first version has three modes for the right panel:

1. **Layout**
   - OCR words or characters positioned according to coordinates in the PDF;
   - white background;
   - optional object rectangles.

2. **PDF order**
   - text in the order in which it is extracted from the PDF without geometric sorting;
   - visible separation of blocks and lines.

3. **Geometric order**
   - text extracted with geometric sorting enabled;
   - intended for direct comparison with the object order stored in the PDF.

The **Overlay** switch displays semi-transparent OCR objects or their rectangles directly over the scan.

### 4.5 Keyboard controls

| Key | Action |
|---|---|
| `↑` / `↓` | previous or next PDF |
| `Page Up` / `Page Down` | previous or next page |
| `1` | mark file as `ok` |
| `2` | mark file as `error` |
| `3` | mark file as `needs_review` |
| `0` | return status to `unreviewed` |
| `Space` | turn overlay on or off |
| `F` | fit to width |
| `Ctrl+G` | go to a specified page |
| `N` | open or focus the note |
| `X` | delete the selected mark, like × on its box; recoverable from Archiv |
| `M` | toggle word/region marking; click a word or drag a rectangle |
| `Esc` | return to text selection / cancel an active rectangle |
| `J` / `K` | next / previous issue in the current filter (`]` / `[` also work) |

When an issue is selected, `N` focuses its note; otherwise it focuses the file note.
Shortcuts do not intercept typing in inputs. Shift + drag marks an area over an
existing issue. Marking also works in the right-hand Layout pane. Issue colors and
labels are independent of the ordinary OCR overlay switch.

After marking a file, automatic advancement to the next unreviewed file can be enabled in the settings.

---

OCR passes run outside the reviewer using the manifest. Red and blue marks both
remain requests for the next pass. Delete satisfactory marks with × on the box;
leave other marks in place. Deleted and legacy confirmed marks are in Archiv,
where Obnovit označení restores a request without changing PDF content.

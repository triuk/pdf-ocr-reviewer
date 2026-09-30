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
| `Space` | turn overlay on or off |
| `F` | reset the image to 100% (fit its left viewport) |
| `Ctrl` + mouse wheel over image | zoom only the image, anchored at the cursor |
| middle-button drag over image | pan the magnified image, including in marking mode |
| `Ctrl+G` | go to a specified page |
| `N` | open or focus the note |
| `X` | delete the selected mark and select the next in the filter, like × on its box; recoverable from Archiv |
| `M` | toggle word/region marking; click a word or drag a rectangle |
| `Esc` | return to text selection / cancel an active rectangle |
| `J` / `K` | next / previous issue in the current filter (`]` / `[` also work) |

When an issue is selected, `N` focuses its note; otherwise it focuses the file note.
Shortcuts do not intercept typing in inputs. Shift + drag marks an area over an
existing issue. Marking also works in the right-hand Layout pane. Issue colors and
labels are independent of the ordinary OCR overlay switch.

The zoom slider changes only the image (25–400%); clicking its percentage resets
to 100%. Right-hand OCR and controls stay the same size. While drawing a box, zoom
is paused so its PDF coordinates stay stable. Ordinary wheel scrolling is unchanged.

Use the **OK** checkbox beside each filename in the left list to record a completed whole-file inspection.
It does not open or switch PDF files. The former 0–3 classification shortcuts are removed.

---

OCR passes run outside the reviewer using the manifest. Red and blue marks both
remain requests for the next pass. Delete satisfactory marks with × on the box;
leave other marks in place. Deleted and legacy confirmed marks are in Archiv,
where Obnovit označení restores a request without changing PDF content.

After deletion, the next mark is selected and scrolled into view in the current
PDF and filter. At the end, selection wraps to the first remaining mark. With no
remaining marks, selection clears; deletion never jumps to a different PDF.

# Left column and shared scroll

### 4.2 Left column

Each file displays:

- an **OK** checkbox for inspection completion;
- name;
- page count after metadata is loaded;
- an indication that the file has changed since the last review;
- number of marked problem pages.

Above the list are filters by name, inspection completion and retained/repaired
marks, plus the number of completed inspections. Completion is independent of
remaining issues. Legacy classifications are preserved in manifest data; only
older `ok` files default to complete.

### 4.3 Center and right columns

Both columns are part of one shared scrolling container. Each page creates one CSS grid row:

```text
page-row
├── scan-viewport
│   └── scan-pane (image, OCR overlay and marks)
└── ocr-pane
```

This prevents two independent scrollbars from gradually drifting out of alignment.

Each row contains:

- page number;
- button for marking a problem page;
- page image on the left;
- OCR display on the right;
- identical dimensions for both panes;
- the aspect ratio of the specific page preserved.

Zoom transforms the scan inside its fixed viewport; the right OCR pane and page
row keep their size. Ctrl + wheel anchors zoom at the cursor. Middle-button drag
pans within page boundaries without creating marks. Selecting an issue pans its
center into view before the shared container scrolls to it. Pan is per page and
resets when opening a document. Zoom is remembered as a UI preference.

Raster refresh is debounced and requests sufficient resolution for the image zoom
(up to the existing 2400-pixel width cap). The previous raster stays visible while
loading, and replacement leaves the annotation/text DOM intact. Zooming out reuses
the existing higher-resolution raster. Stale render generations remain rejected.

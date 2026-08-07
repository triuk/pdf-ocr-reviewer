# Left column and shared scroll

### 4.2 Left column

Each file displays:

- review status;
- name;
- page count after metadata is loaded;
- an indication that the file has changed since the last review;
- number of marked problem pages.

Statuses:

- `unreviewed` – not reviewed;
- `ok` – OK;
- `error` – OCR error found;
- `needs_review` – requires further review.

Above the list:

- text filter by name;
- filter by status;
- summary counts of files in each status.

### 4.3 Center and right columns

Both columns are part of one shared scrolling container. Each page creates one CSS grid row:

```text
page-row
├── scan-pane
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

# User interface design

## 4. User interface design

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Open folder | path | OCR mode | overlay | zoom | review status             │
├──────────────────┬──────────────────────────┬───────────────────────────────┤
│ PDF files        │ Scan                     │ OCR layer                     │
│                  │                          │                               │
│ ○ file-01.pdf    │ ┌──────────────────────┐ │ ┌───────────────────────────┐ │
│ ✓ file-02.pdf    │ │ page 1               │ │ │ OCR for page 1            │ │
│ ! file-03.pdf    │ └──────────────────────┘ │ └───────────────────────────┘ │
│ ? file-04.pdf    │                          │                               │
│                  │ ┌──────────────────────┐ │ ┌───────────────────────────┐ │
│ Filter           │ │ page 2               │ │ │ OCR for page 2            │ │
│ Status           │ └──────────────────────┘ │ └───────────────────────────┘ │
└──────────────────┴──────────────────────────┴───────────────────────────────┘
```

### 4.1 Top toolbar

- **Open folder** button;
- current path display;
- OCR mode selector;
- switch for OCR overlay over the scan;
- zoom slider;
- buttons or keyboard actions for file status;
- unsaved-changes indicator and manifest errors when applicable.

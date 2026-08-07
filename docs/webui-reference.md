# WebUI reference and user interface

## 3. WebUI reference project

The design is based on the supplied `example-webui-python.zip` archive.

### Identified reference version

- main repository: commit `538123e061622a702709a1dd9c5a22cd32592dd3`;
- UI submodule: commit `72070fe146df89d3e0a6325a0475783bfda6d40d`;
- Python dependency in the example: `webui2`;
- the frontend is separated in the `ui/` folder;
- the backend uses a single `WebUIApp` class and functions bound through `window.bind()`.

### Elements we will adopt

1. **Backend/frontend separation**
   - Python in its own application layer;
   - `ui/index.html`, `ui/index.js`, and manually maintained `ui/index.css`;
   - no SCSS or CSS build step.

2. **WebUI lifecycle**
   - `set_root_folder()` for the frontend;
   - opening with `show("index.html")`;
   - keeping the application alive with `webui.wait()`;
   - no separate user-facing or development `--server` mode; WebUI's internal local transport remains an implementation detail only.

3. **Bidirectional calls**
   - the frontend calls Python through functions registered with `window.bind()`;
   - Python returns small responses as JSON strings;
   - larger binary data can be sent through `send_raw()`.

4. **Synchronization after connection**
   - `webui.setEventCallback()`;
   - on the `CONNECTED` event, the frontend calls `syncStateB()`;
   - a generic function applies state to HTML elements according to their `id`;
   - a guard flag prevents state restoration from triggering control events in reverse.

5. **Reusable control principles**
   - switch-style toggles;
   - a simple slider;
   - CSS variables;
   - automatic light and dark mode through `prefers-color-scheme`;
   - system fonts and no external CDN.

   The application's visual style will be designed separately for OCR review needs. Button appearance and the overall page style are not copied from the reference project.

6. **File save/export**
   - the reference approach using `showSaveFilePicker()` with a download fallback is used for CSV export.

### Elements we will not adopt

- Chart.js chart;
- dual noUiSlider;
- periodic generation of test data;
- generic frontend as a Git submodule.

This application's UI is too specific, so the reference project is used as a starting pattern rather than a permanently linked submodule.

---

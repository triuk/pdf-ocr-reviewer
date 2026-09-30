async function requestPage(pageIndex) {
  if (state.navigating || !state.document) return;
  const existing = [...state.pendingRequests.values()].find((value) => value.pageIndex === pageIndex);
  if (existing) return;

  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  const scanPane = row?.querySelector(".scan-pane");
  const targetWidth = Math.max(300, Math.min(2400, Math.round((scanPane?.clientWidth || 800) * Math.max(1, state.ui.zoom_percent / 100) * devicePixelRatio)));
  if ((state.pageData.get(pageIndex)?.targetWidth || 0) >= targetWidth) return;
  const uniquePart = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  const requestId = `${state.generation}:${pageIndex}:${uniquePart}`;
  const generation = state.generation;
  const renderGeneration = state.renderGeneration;
  state.pendingRequests.set(requestId, { pageIndex, generation: state.generation, renderGeneration, targetWidth });
  try {
    await callBackend("requestPageB", requestId, state.document.file_id, pageIndex, targetWidth);
  } catch (error) {
    state.pendingRequests.delete(requestId);
    if (generation === state.generation && renderGeneration === state.renderGeneration) showToast(error.message, true);
  }
}

function pageReadyF(rawData) {
  try {
    const bytes = rawData instanceof Uint8Array ? rawData : new Uint8Array(rawData);
    if (bytes.byteLength < 4) throw new Error("Binary page packet is too short.");
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const headerLength = view.getUint32(0, true);
    const headerStart = 4;
    const headerEnd = headerStart + headerLength;
    if (headerEnd > bytes.byteLength) throw new Error("Binary page packet has an invalid header length.");
    const header = JSON.parse(new TextDecoder().decode(bytes.subarray(headerStart, headerEnd)));
    const pending = state.pendingRequests.get(header.request_id);
    state.pendingRequests.delete(header.request_id);
    if (!pending || pending.generation !== state.generation || pending.renderGeneration !== state.renderGeneration || header.file_id !== state.activeFileId) return;

    const imageBytes = bytes.subarray(headerEnd);
    const blob = new Blob([imageBytes], { type: header.mime });
    const objectUrl = URL.createObjectURL(blob);
    const oldUrl = state.objectUrls.get(header.page_index);
    if (oldUrl) URL.revokeObjectURL(oldUrl);
    state.objectUrls.set(header.page_index, objectUrl);
    const wasLoaded = state.pageData.has(header.page_index);
    state.pageData.set(header.page_index, { header, objectUrl, targetWidth: pending.targetWidth });
    const displayed = elements.pagesId.querySelector(`[data-page-index="${header.page_index}"] .scan-pane img`);
    if (wasLoaded && displayed) displayed.src = objectUrl;
    else renderLoadedPage(header.page_index);
    pruneLoadedPages();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderLoadedPage(pageIndex) {
  const loaded = state.pageData.get(pageIndex);
  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  if (!loaded || !row) return;
  const scanPane = row.querySelector(".scan-pane");
  const ocrPane = row.querySelector(".ocr-pane");
  scanPane.replaceChildren();
  ocrPane.replaceChildren();

  const image = document.createElement("img");
  image.src = loaded.objectUrl;
  image.alt = `Scan of page ${pageIndex + 1}`;
  image.draggable = false;
  scanPane.append(image);

  const textLayer = document.createElement("div");
  textLayer.className = "scan-text-layer";
  textLayer.setAttribute("aria-hidden", "true");
  renderSelectableTextLayer(textLayer, loaded.header.ocr);
  scanPane.append(textLayer);

  const overlay = document.createElement("div");
  overlay.className = "scan-overlay";
  overlay.classList.toggle("visible", Boolean(state.ui.overlay));
  renderLayoutItems(overlay, loaded.header.ocr);
  scanPane.append(overlay);

  renderOcrPane(ocrPane, loaded.header.ocr);
  bindRegionMarking(scanPane, pageIndex, loaded.header.ocr);
  // The right pane is selectable spatially only in Layout mode.
  ocrPane.markingAbortController?.abort();
  if (state.ui.ocr_mode === "layout") bindRegionMarking(ocrPane, pageIndex, loaded.header.ocr);
  renderPageIssues(pageIndex);
}

function renderOcrPane(pane, ocr) {
  const selectedText = state.ui.ocr_mode === "pdf_order" ? ocr.pdf_order : ocr.geometric_order;
  if (state.ui.ocr_mode === "layout") {
    if (!ocr.layout_items.length) {
      const empty = document.createElement("div");
      empty.className = "page-placeholder";
      empty.textContent = "The OCR layer is empty.";
      pane.append(empty);
      return;
    }
    const layout = document.createElement("div");
    layout.className = "ocr-layout";
    renderLayoutItems(layout, ocr);
    pane.append(layout);
    return;
  }
  const pre = document.createElement("pre");
  pre.className = "ocr-text";
  pre.textContent = selectedText || "The OCR layer is empty.";
  pane.append(pre);
}

function renderSelectableTextLayer(container, ocr) {
  const runs = selectableTextRuns(ocr.layout_items);
  for (let index = 0; index < runs.length; index += 1) {
    const run = runs[index];
    const span = document.createElement("span");
    span.className = "scan-text-run";
    span.textContent = run.items.map((item) => item.text).join(" ");
    placeOcrText(span, run, ocr, false);
    span.setAttribute("role", "presentation");
    container.append(span);

    const next = runs[index + 1];
    if (!next) continue;
    appendSelectableBreak(container);
    if (next.block !== run.block) appendSelectableBreak(container);
  }

  const endOfContent = document.createElement("div");
  endOfContent.className = "scan-text-end";
  container.append(endOfContent);
  bindSelectableTextLayer(container);

  requestAnimationFrame(() => fitSelectableTextRuns(container));
}

function selectableTextRuns(items) {
  const runs = [];
  let current = null;
  for (const item of items) {
    if (!current || current.block !== item.block || current.line !== item.line) {
      current = {
        block: item.block,
        line: item.line,
        x0: item.x0,
        y0: item.y0,
        x1: item.x1,
        y1: item.y1,
        items: [],
      };
      runs.push(current);
    }
    current.items.push(item);
    current.x0 = Math.min(current.x0, item.x0);
    current.y0 = Math.min(current.y0, item.y0);
    current.x1 = Math.max(current.x1, item.x1);
    current.y1 = Math.max(current.y1, item.y1);
  }
  return runs;
}

function appendSelectableBreak(container) {
  const br = document.createElement("br");
  br.className = "scan-text-break";
  br.setAttribute("role", "presentation");
  container.append(br);
}

function bindSelectableTextLayer(container) {
  container.addEventListener("pointerdown", () => {
    container.classList.add("selecting");
    const controller = new AbortController();
    const finish = () => {
      container.classList.remove("selecting");
      controller.abort();
    };
    document.addEventListener("pointerup", finish, { signal: controller.signal });
    window.addEventListener("blur", finish, { signal: controller.signal });
    document.addEventListener(
      "keyup",
      (event) => {
        if (event.key === "Escape") finish();
      },
      { signal: controller.signal },
    );
  });
}

function fitSelectableTextRuns(container) {
  if (!container.isConnected) return;
  for (const run of container.querySelectorAll(".scan-text-run")) {
    const naturalWidth = run.offsetWidth;
    const targetWidth = Number(run.dataset.targetWidthRatio)
      * (run.dataset.widthAxis === "height" ? container.clientHeight : container.clientWidth);
    if (naturalWidth <= 0 || targetWidth <= 0) continue;
    const scaleX = Math.max(0.05, Math.min(20, targetWidth / naturalWidth));
    run.style.transform = `rotate(${run.dataset.rotation || 0}deg) scaleX(${scaleX})`;
  }
}

function renderLayoutItems(container, ocr) {
  for (const item of ocr.layout_items) {
    const span = document.createElement("span");
    span.className = "ocr-word";
    span.textContent = item.text;
    placeOcrText(span, item, ocr, true);
    container.append(span);
  }
}

function placeOcrText(span, item, ocr, sizeBox) {
  const rotation = ocr.rotation || 0;
  const vertical = rotation === 90 || rotation === 270;
  const width = (item.x1 - item.x0) / ocr.page_width;
  const height = (item.y1 - item.y0) / ocr.page_height;
  const left = rotation === 90 || rotation === 180 ? item.x1 : item.x0;
  const top = rotation === 180 || rotation === 270 ? item.y1 : item.y0;
  span.style.left = `${left / ocr.page_width * 100}%`;
  span.style.top = `${top / ocr.page_height * 100}%`;
  span.style.transform = `rotate(${rotation}deg)`;
  span.dataset.rotation = String(rotation);
  span.dataset.widthAxis = vertical ? "height" : "width";
  span.dataset.targetWidthRatio = String(vertical ? height : width);
  span.style.fontSize = `${Math.max(0.5, (vertical ? width : height) * 82)}${vertical ? "cqw" : "cqh"}`;
  if (sizeBox) {
    span.style.width = vertical ? `${height * 100}cqh` : `${width * 100}%`;
    span.style.height = vertical ? `${width * 100}cqw` : `${height * 100}%`;
  }
}

function unloadPage(pageIndex) {
  if (state.markingDrag?.pane.closest(`[data-page-index="${pageIndex}"]`)) state.markingDrag.cleanup();
  const url = state.objectUrls.get(pageIndex);
  if (url) URL.revokeObjectURL(url);
  state.objectUrls.delete(pageIndex);
  state.pageData.delete(pageIndex);
  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  if (!row || !state.document) return;
  const page = state.document.pages[pageIndex];
  const scanPane = row.querySelector(".scan-pane");
  const ocrPane = row.querySelector(".ocr-pane");
  scanPane.markingAbortController?.abort();
  ocrPane.markingAbortController?.abort();
  scanPane.replaceChildren(createPlaceholder("Load when nearby…"));
  ocrPane.replaceChildren(createPlaceholder("Load when nearby…"));
  scanPane.style.aspectRatio = `${page.width} / ${page.height}`;
  ocrPane.style.aspectRatio = `${page.width} / ${page.height}`;
}

function createPlaceholder(text) {
  const placeholder = document.createElement("div");
  placeholder.className = "page-placeholder";
  placeholder.textContent = text;
  return placeholder;
}

function pruneLoadedPages() {
  const maximumLoadedPages = 8;
  if (state.pageData.size <= maximumLoadedPages) return;
  const protectedPages = state.visiblePages;
  const candidates = [...state.pageData.keys()].filter((pageIndex) => !protectedPages.has(pageIndex));
  const center = protectedPages.size ? [...protectedPages][0] : 0;
  candidates.sort((a, b) => Math.abs(b - center) - Math.abs(a - center));
  while (state.pageData.size > maximumLoadedPages && candidates.length) {
    unloadPage(candidates.shift());
  }
}

function rerenderLoadedOcr() {
  for (const [pageIndex] of state.pageData) renderLoadedPage(pageIndex);
}

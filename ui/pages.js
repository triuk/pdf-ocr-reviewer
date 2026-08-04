async function requestPage(pageIndex) {
  if (!state.document || state.pageData.has(pageIndex)) return;
  const existing = [...state.pendingRequests.values()].find((value) => value.pageIndex === pageIndex);
  if (existing) return;

  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  const scanPane = row?.querySelector(".scan-pane");
  const targetWidth = Math.max(300, Math.min(2400, Math.round((scanPane?.clientWidth || 800) * devicePixelRatio)));
  const uniquePart = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  const requestId = `${state.generation}:${pageIndex}:${uniquePart}`;
  state.pendingRequests.set(requestId, { pageIndex, generation: state.generation });
  try {
    await callBackend("requestPageB", requestId, state.document.file_id, pageIndex, targetWidth);
  } catch (error) {
    state.pendingRequests.delete(requestId);
    showToast(error.message, true);
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
    if (!pending || pending.generation !== state.generation || header.file_id !== state.activeFileId) return;

    const imageBytes = bytes.subarray(headerEnd);
    const blob = new Blob([imageBytes], { type: header.mime });
    const objectUrl = URL.createObjectURL(blob);
    const oldUrl = state.objectUrls.get(header.page_index);
    if (oldUrl) URL.revokeObjectURL(oldUrl);
    state.objectUrls.set(header.page_index, objectUrl);
    state.pageData.set(header.page_index, { header, objectUrl });
    renderLoadedPage(header.page_index);
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
  image.alt = `Sken strany ${pageIndex + 1}`;
  scanPane.append(image);

  const overlay = document.createElement("div");
  overlay.className = "scan-overlay";
  overlay.classList.toggle("visible", Boolean(state.ui.overlay));
  renderLayoutItems(overlay, loaded.header.ocr);
  scanPane.append(overlay);

  renderOcrPane(ocrPane, loaded.header.ocr);
}

function renderOcrPane(pane, ocr) {
  const selectedText = state.ui.ocr_mode === "pdf_order" ? ocr.pdf_order : ocr.geometric_order;
  if (state.ui.ocr_mode === "layout") {
    if (!ocr.layout_items.length) {
      const empty = document.createElement("div");
      empty.className = "page-placeholder";
      empty.textContent = "OCR vrstva je prázdná.";
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
  pre.textContent = selectedText || "OCR vrstva je prázdná.";
  pane.append(pre);
}

function renderLayoutItems(container, ocr) {
  for (const item of ocr.layout_items) {
    const span = document.createElement("span");
    span.className = "ocr-word";
    span.textContent = item.text;
    span.style.left = `${(item.x0 / ocr.page_width) * 100}%`;
    span.style.top = `${(item.y0 / ocr.page_height) * 100}%`;
    span.style.width = `${((item.x1 - item.x0) / ocr.page_width) * 100}%`;
    span.style.height = `${((item.y1 - item.y0) / ocr.page_height) * 100}%`;
    const fontPercent = Math.max(0.5, ((item.y1 - item.y0) / ocr.page_height) * 100 * 0.82);
    span.style.fontSize = `${fontPercent}cqh`;
    container.append(span);
  }
}

function unloadPage(pageIndex) {
  const url = state.objectUrls.get(pageIndex);
  if (url) URL.revokeObjectURL(url);
  state.objectUrls.delete(pageIndex);
  state.pageData.delete(pageIndex);
  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  if (!row || !state.document) return;
  const page = state.document.pages[pageIndex];
  const scanPane = row.querySelector(".scan-pane");
  const ocrPane = row.querySelector(".ocr-pane");
  scanPane.replaceChildren(createPlaceholder("Načíst při přiblížení…"));
  ocrPane.replaceChildren(createPlaceholder("Načíst při přiblížení…"));
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

function applyZoom(reloadVisiblePages = true) {
  if (!elements.pagesId) return;
  elements.pagesId.style.width = `${state.ui.zoom_percent}%`;
  if (!reloadVisiblePages || !state.document) return;
  const visible = [...state.visiblePages];
  for (const pageIndex of [...state.pageData.keys()]) unloadPage(pageIndex);
  for (const pageIndex of visible) requestPage(pageIndex);
}

function rerenderLoadedOcr() {
  for (const [pageIndex] of state.pageData) renderLoadedPage(pageIndex);
}


"use strict";

function constrainScanView(view) {
  const limit = 1 - view.scale;
  const clamp = value => view.scale < 1 ? limit / 2 : Math.max(limit, Math.min(0, value));
  return { scale: view.scale, x: clamp(view.x), y: clamp(view.y) };
}

function zoomScanView(view, scale, anchor = { x: 0.5, y: 0.5 }) {
  const ratio = scale / view.scale;
  return constrainScanView({ scale,
    x: anchor.x - (anchor.x - view.x) * ratio,
    y: anchor.y - (anchor.y - view.y) * ratio });
}

function scanView(pageIndex) {
  return state.scanViews.get(pageIndex) || { scale: 1, x: 0, y: 0 };
}

function renderScanView(pageIndex) {
  const pane = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"] .scan-pane`);
  if (!pane) return;
  const view = scanView(pageIndex);
  pane.style.transform = `translate(${view.x * 100}%, ${view.y * 100}%) scale(${view.scale})`;
}

function applyZoom(reloadVisiblePages = true, anchor = null) {
  if (!elements.pagesId) return;
  const percent = Math.max(25, Math.min(400, Math.round(Number(state.ui.zoom_percent) || 100)));
  state.ui.zoom_percent = percent;
  elements.zoomId.value = percent;
  elements.zoomValueId.textContent = `${percent} %`;
  for (const page of state.document?.pages || []) {
    state.scanViews.set(page.page_index, zoomScanView(scanView(page.page_index), percent / 100,
      anchor?.pageIndex === page.page_index ? anchor : undefined));
    renderScanView(page.page_index);
  }
  if (!reloadVisiblePages || !state.document) return;
  // Reject old raster replies immediately, but keep the displayed image and OCR DOM.
  state.renderGeneration += 1;
  state.pendingRequests.clear();
  state.renderQueue.clear();
  window.clearTimeout(state.zoomRenderTimer);
  const context = captureContext();
  state.zoomRenderTimer = window.setTimeout(() => {
    if (!contextMatches(context)) return;
    for (const pageIndex of state.visiblePages) requestPage(pageIndex);
  }, 180);
}

function setScanZoom(percent, anchor = null) {
  if (state.navigating || state.markingDrag || state.scanPan) return;
  percent = Math.max(25, Math.min(400, Math.round(percent)));
  if (!Number.isFinite(percent) || percent === state.ui.zoom_percent) return;
  state.ui.zoom_percent = percent;
  applyZoom(true, anchor);
  saveUiOptions({ zoom_percent: percent });
}

function focusScanIssue(issue) {
  const view = scanView(issue.page_index);
  const x = (issue.bbox[0] + issue.bbox[2]) / 2 / issue.page_width;
  const y = (issue.bbox[1] + issue.bbox[3]) / 2 / issue.page_height;
  state.scanViews.set(issue.page_index, constrainScanView({ scale: view.scale,
    x: 0.5 - x * view.scale, y: 0.5 - y * view.scale }));
  renderScanView(issue.page_index);
}

function bindScanViewport(viewport, pageIndex) {
  let wheelValue = state.ui.zoom_percent;
  let wheelAt = 0;
  let lastWheelZoom = wheelValue;
  viewport.addEventListener("wheel", event => {
    if (!event.ctrlKey) return;
    // Suppress browser-wide zoom even while a marking or pan gesture is active.
    event.preventDefault();
    event.stopPropagation();
    if (state.navigating || state.markingDrag || state.scanPan || event.buttons) return;
    const now = performance.now();
    if (now - wheelAt > 250 || state.ui.zoom_percent !== lastWheelZoom) wheelValue = state.ui.zoom_percent;
    wheelAt = now;
    const units = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1;
    const delta = Math.max(-240, Math.min(240, event.deltaY * units));
    wheelValue = Math.max(25, Math.min(400, wheelValue * Math.exp(-delta * 0.0015)));
    const rect = viewport.getBoundingClientRect();
    setScanZoom(wheelValue, { pageIndex,
      x: (event.clientX - rect.left - viewport.clientLeft) / viewport.clientWidth,
      y: (event.clientY - rect.top - viewport.clientTop) / viewport.clientHeight });
    lastWheelZoom = state.ui.zoom_percent;
  }, { passive: false });

  viewport.addEventListener("pointerdown", event => {
    if (event.button !== 1) return;
    event.preventDefault();
    event.stopPropagation();
    if (state.navigating || state.markingDrag || state.scanPan || scanView(pageIndex).scale <= 1) return;
    const initial = scanView(pageIndex);
    const start = { x: event.clientX, y: event.clientY };
    const controller = new AbortController();
    const options = { signal: controller.signal };
    const cleanup = () => {
      controller.abort();
      viewport.classList.remove("panning");
      state.scanPan = null;
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    };
    state.scanPan = { cleanup };
    viewport.classList.add("panning");
    viewport.setPointerCapture(event.pointerId);
    viewport.addEventListener("pointermove", move => {
      state.scanViews.set(pageIndex, constrainScanView({ scale: initial.scale,
        x: initial.x + (move.clientX - start.x) / viewport.clientWidth,
        y: initial.y + (move.clientY - start.y) / viewport.clientHeight }));
      renderScanView(pageIndex);
    }, options);
    viewport.addEventListener("pointerup", cleanup, options);
    viewport.addEventListener("pointercancel", cleanup, options);
    viewport.addEventListener("lostpointercapture", cleanup, options);
    window.addEventListener("blur", cleanup, options);
    document.addEventListener("keydown", key => { if (key.key === "Escape") cleanup(); }, options);
  }, { capture: true });
  viewport.addEventListener("auxclick", event => { if (event.button === 1) event.preventDefault(); });
}

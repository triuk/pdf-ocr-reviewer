async function setFileStatusF(status) {
  if (!state.activeFileId) return;
  try {
    await callBackend("setFileStatusB", state.activeFileId, status);
    const file = state.files.find((item) => item.file_id === state.activeFileId);
    if (file) {
      file.status = status;
      file.changed_since_review = false;
    }
    if (state.document) state.document.status = status;
    setActiveStatus(status);
    renderFileList();
    if (state.ui.auto_advance && status !== "unreviewed") await moveDocument(1, true);
  } catch (error) {
    showToast(error.message, true);
  }
}

function setActiveStatus(status) {
  document.querySelectorAll(".status-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.status === status);
  });
}

async function toggleProblemPageF(pageIndex, button) {
  if (!state.activeFileId) return;
  try {
    const data = await callBackend("toggleProblemPageB", state.activeFileId, pageIndex);
    state.document.problem_pages = data.problem_pages;
    button.classList.toggle("active", data.selected);
    const file = state.files.find((item) => item.file_id === state.activeFileId);
    if (file) file.problem_page_count = data.problem_pages.length;
    renderFileList();
  } catch (error) {
    showToast(error.message, true);
  }
}

function scheduleSavePosition(pageIndex) {
  if (!state.activeFileId) return;
  window.clearTimeout(state.savePositionTimer);
  const fileId = state.activeFileId;
  state.savePositionTimer = window.setTimeout(async () => {
    try { await callBackend("setLastPageB", fileId, pageIndex); }
    catch (error) { showToast(error.message, true); }
  }, 700);
}

function scheduleSaveNote() {
  if (!state.activeFileId) return;
  window.clearTimeout(state.saveNoteTimer);
  const fileId = state.activeFileId;
  const note = elements.fileNoteId.value;
  state.saveNoteTimer = window.setTimeout(async () => {
    try { await callBackend("setFileNoteB", fileId, note); }
    catch (error) { showToast(error.message, true); }
  }, 500);
}

async function saveUiOptions(patch) {
  state.ui = { ...state.ui, ...patch };
  try { await callBackend("setUiOptionsB", JSON.stringify(patch)); }
  catch (error) { showToast(error.message, true); }
}

function releasePageResources() {
  if (state.observer) state.observer.disconnect();
  for (const url of state.objectUrls.values()) URL.revokeObjectURL(url);
  state.objectUrls.clear();
  state.pageData.clear();
  state.pendingRequests.clear();
  state.visiblePages.clear();
}

function resetViewportScroll() {
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  window.scrollTo(0, 0);
}

function scrollPageRowInsideContainer(row, behavior = "auto") {
  if (!row) return;

  const container = elements.pageScrollId;
  const containerRect = container.getBoundingClientRect();
  const rowRect = row.getBoundingClientRect();
  const targetTop = Math.max(
    0,
    container.scrollTop + rowRect.top - containerRect.top - 8,
  );

  container.scrollTo({ top: targetTop, behavior });
  resetViewportScroll();
}

function scrollToSavedPage(pageIndex) {
  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  scrollPageRowInsideContainer(row);
}

async function moveDocument(direction, unreviewedOnly = false) {
  if (!state.files.length) return;
  const currentIndex = Math.max(0, state.files.findIndex((file) => file.file_id === state.activeFileId));
  for (let step = 1; step <= state.files.length; step += 1) {
    const index = (currentIndex + direction * step + state.files.length) % state.files.length;
    const candidate = state.files[index];
    if (!unreviewedOnly || candidate.status === "unreviewed") {
      await openDocumentF(candidate.file_id);
      return;
    }
  }
}

function movePage(direction) {
  const rows = [...elements.pagesId.querySelectorAll(".page-row")];
  if (!rows.length) return;
  const scrollTop = elements.pageScrollId.scrollTop;
  let index = rows.findIndex((row) => row.offsetTop >= scrollTop + 10);
  if (index < 0) index = rows.length - 1;
  index = Math.max(0, Math.min(rows.length - 1, index + direction));
  scrollPageRowInsideContainer(rows[index]);
}

function handleKeyboard(event) {
  const target = event.target;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return;
  if (event.key === "ArrowDown") { event.preventDefault(); moveDocument(1); }
  else if (event.key === "ArrowUp") { event.preventDefault(); moveDocument(-1); }
  else if (event.key === "PageDown") { event.preventDefault(); movePage(1); }
  else if (event.key === "PageUp") { event.preventDefault(); movePage(-1); }
  else if (["0", "1", "2", "3"].includes(event.key)) {
    const status = { "0": "unreviewed", "1": "ok", "2": "error", "3": "needs_review" }[event.key];
    setFileStatusF(status);
  } else if (event.code === "Space") {
    event.preventDefault();
    elements.overlayId.checked = !elements.overlayId.checked;
    elements.overlayId.dispatchEvent(new Event("change"));
  } else if (event.key.toLocaleLowerCase("cs") === "n") {
    elements.fileNoteId.focus();
  }
}

function attachEvents() {
  elements.selectFolderId.addEventListener("click", selectFolderF);
  elements.openPathId.addEventListener("click", openPathF);
  elements.folderPathId.addEventListener("keydown", (event) => { if (event.key === "Enter") openPathF(); });
  elements.refreshFolderId.addEventListener("click", refreshFolderF);
  elements.exportCsvId.addEventListener("click", exportCsvF);
  elements.ocrModeId.addEventListener("change", () => {
    if (state.applyingState) return;
    saveUiOptions({ ocr_mode: elements.ocrModeId.value });
    rerenderLoadedOcr();
  });
  elements.overlayId.addEventListener("change", () => {
    if (state.applyingState) return;
    saveUiOptions({ overlay: elements.overlayId.checked });
    rerenderLoadedOcr();
  });
  elements.zoomId.addEventListener("input", () => { elements.zoomValueId.value = `${elements.zoomId.value} %`; });
  elements.zoomId.addEventListener("change", () => {
    const zoomPercent = Number(elements.zoomId.value);
    saveUiOptions({ zoom_percent: zoomPercent });
    applyZoom(true);
  });
  elements.nameFilterId.addEventListener("input", () => {
    renderFileList();
    saveUiOptions({ name_filter: elements.nameFilterId.value });
  });
  elements.statusFilterId.addEventListener("change", () => {
    renderFileList();
    saveUiOptions({ status_filter: elements.statusFilterId.value });
  });
  elements.fileNoteId.addEventListener("input", scheduleSaveNote);
  document.querySelectorAll(".status-button").forEach((button) => {
    button.addEventListener("click", () => setFileStatusF(button.dataset.status));
  });
  document.addEventListener("keydown", handleKeyboard);
}

document.addEventListener("DOMContentLoaded", () => {
  bindElements();
  attachEvents();
  resetViewportScroll();
  if (typeof webui === "undefined") {
    showToast("Soubor webui.js nebyl načten.", true);
    return;
  }
  webui.setEventCallback(async (eventType) => {
    if (eventType === webui.event.CONNECTED) {
      try { await syncStateF(); }
      catch (error) { showToast(error.message, true); }
    } else if (eventType === webui.event.DISCONNECTED) {
      showToast("Spojení s backendem bylo ukončeno.", true);
    }
  });
});

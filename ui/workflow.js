async function setFileStatusF(status) {
  const context = captureContext();
  if (!state.activeFileId || state.navigating) return;
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
    if (contextMatches(context) && state.ui.auto_advance && status !== "unreviewed") await moveDocument(1, true);
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
  if (!state.activeFileId || state.navigating) return;
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

function getCurrentPageIndex() {
  const rows = [...elements.pagesId.querySelectorAll(".page-row")];
  if (!rows.length) return 0;

  const containerTop = elements.pageScrollId.getBoundingClientRect().top + 12;
  let nearestIndex = Number(rows[0].dataset.pageIndex);
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (const row of rows) {
    const rect = row.getBoundingClientRect();
    const pageIndex = Number(row.dataset.pageIndex);

    if (rect.top <= containerTop && rect.bottom > containerTop) {
      return pageIndex;
    }

    const distance = Math.abs(rect.top - containerTop);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = pageIndex;
    }
  }

  return nearestIndex;
}

function scheduleSaveCurrentPage() {
  if (!state.activeFileId || !state.document) return;
  window.clearTimeout(state.savePositionTimer);
  const fileId = state.activeFileId;

  state.savePositionTimer = window.setTimeout(async () => {
    if (fileId !== state.activeFileId || state.navigating) return;
    const pageIndex = getCurrentPageIndex();
    try {
      await callBackend("setLastPageB", fileId, pageIndex);
    } catch (error) {
      showToast(error.message, true);
    }
  }, 450);
}

function scheduleSaveNote() {
  if (!state.activeFileId || state.navigating) return;
  window.clearTimeout(state.saveNoteTimer);
  const prior = state.fileNoteDraft;
  state.fileNoteDraft = { folder: state.folder, fileId: state.activeFileId, note: elements.fileNoteId.value,
    token: crypto.randomUUID(), base_revision: state.document.manifest_revision, expected_sha256: prior?.expected_sha256 || state.document.ocr_sha256,
    base_note: prior?.base_note ?? state.document.note, recovered: Boolean(prior?.recovered) };
  persistDraft(state.fileNoteDraft);
  state.saveNoteTimer = window.setTimeout(flushFileNote, 500);
}

function flushFileNote() {
  window.clearTimeout(state.saveNoteTimer);
  const job = state.fileNoteQueue.then(async () => {
    while (state.fileNoteDraft) {
      const draft = state.fileNoteDraft;
      if (draft.recovered) return true;
      if (draft.folder !== state.folder) return false;
      await state.journalQueue;
      try {
        await callBackend("setFileNoteB", draft.fileId, draft.note);
        if (state.fileNoteDraft === draft) state.fileNoteDraft = null;
        state.document.note = draft.note;
        forgetDraft(draft);
        setSaveState("Manifest uložen", false);
      } catch (error) { showToast(error.message, true); return false; }
    }
    return true;
  });
  state.fileNoteQueue = job.catch(() => false);
  return job;
}

async function saveUiOptions(patch) {
  state.ui = { ...state.ui, ...patch };
  try { await callBackend("setUiOptionsB", JSON.stringify(patch)); }
  catch (error) { showToast(error.message, true); }
}

function releasePageResources() {
  if (state.observer) state.observer.disconnect();
  window.clearTimeout(state.savePositionTimer);
  for (const url of state.objectUrls.values()) URL.revokeObjectURL(url);
  state.objectUrls.clear();
  state.pageData.clear();
  state.pendingRequests.clear();
  state.visiblePages.clear();
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
}

function scrollToSavedPage(pageIndex) {
  if (!state.document?.pages?.length) {
    elements.pageScrollId.scrollTop = 0;
    return;
  }

  const maximumIndex = state.document.pages.length - 1;
  const safeIndex = Math.max(0, Math.min(maximumIndex, Number(pageIndex) || 0));
  const row = elements.pagesId.querySelector(`[data-page-index="${safeIndex}"]`);
  scrollPageRowInsideContainer(row);
}

async function moveDocument(direction, unreviewedOnly = false) {
  const candidates = filteredFiles().filter(file => !unreviewedOnly || file.status === "unreviewed");
  if (!candidates.length) return;
  const currentIndex = state.files.findIndex(file => file.file_id === state.activeFileId);
  if (direction < 0) candidates.reverse();
  const after = candidates.find(file => direction * (state.files.indexOf(file) - currentIndex) > 0);
  const next = after || candidates[0];
  if (next.file_id !== state.activeFileId) await openDocumentF(next.file_id);
}

function movePage(direction) {
  const rows = [...elements.pagesId.querySelectorAll(".page-row")];
  if (!rows.length) return;

  const currentIndex = getCurrentPageIndex();
  const targetIndex = Math.max(0, Math.min(rows.length - 1, currentIndex + direction));
  const targetRow = elements.pagesId.querySelector(`[data-page-index="${targetIndex}"]`);
  scrollPageRowInsideContainer(targetRow, "smooth");
}

function handleKeyboard(event) {
  if (state.navigating) return;
  const target = event.target;
  if (event.key === "Escape") {
    setMarking(false);
    if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) target.blur();
    return;
  }
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return;
  if (handleIssueKeyboard(event)) return;
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
  elements.fileIssueFilterId.addEventListener("change", () => {
    renderFileList();
    saveUiOptions({ issue_filter: elements.fileIssueFilterId.value });
  });
  elements.reviewRepairsId.addEventListener("click", startRepairReview);
  elements.fileNoteId.addEventListener("input", scheduleSaveNote);
  elements.pageScrollId.addEventListener("scroll", scheduleSaveCurrentPage, { passive: true });
  document.querySelectorAll(".status-button").forEach((button) => {
    button.addEventListener("click", () => setFileStatusF(button.dataset.status));
  });
  document.addEventListener("keydown", handleKeyboard);
}

document.addEventListener("DOMContentLoaded", () => {
  bindElements();
  attachEvents();
  attachIssueEvents();
  attachRecoveryEvents();
  if (typeof webui === "undefined") {
    showToast("The webui.js file was not loaded.", true);
    return;
  }
  webui.setEventCallback(async (eventType) => {
    if (eventType === webui.event.CONNECTED) {
      try { await syncStateF(); }
      catch (error) { showToast(error.message, true); }
    } else if (eventType === webui.event.DISCONNECTED) {
      showToast("The backend connection was closed.", true);
    }
  });
});

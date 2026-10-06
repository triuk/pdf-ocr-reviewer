async function setReviewCompleteF(complete, fileId = state.activeFileId) {
  const file = state.files.find(item => item.file_id === fileId);
  if (!file || state.navigating || state.reviewBusy) return;
  const payload = { complete, expected_identity: file.identity_token };
  if (fileId === state.activeFileId && state.document) payload.expected_sha256 = state.document.ocr_sha256;
  state.reviewBusy = true;
  renderFileList();
  try {
    const data = await callBackend("setReviewCompleteB", fileId, JSON.stringify(payload));
    Object.assign(file, data);
    if (fileId === state.activeFileId && state.document) state.document.review_complete = data.review_complete;
    setSaveState("Manifest uložen", false);
  } catch (error) { showToast(error.message, true); }
  finally { state.reviewBusy = false; renderFileList(); }
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

async function setRepairAcceptanceF(accepted, fileId = state.activeFileId) {
  const file = state.files.find(item => item.file_id === fileId);
  if (!file || !state.document || fileId !== state.activeFileId || state.navigating || state.reviewBusy) return;
  const context = captureContext();
  const payload = { accepted, expected_identity: state.document.identity_token,
    expected_sha256: state.document.ocr_sha256 };
  state.reviewBusy = true;
  renderFileList();
  try {
    if (!await flushIssueDraft() || !await flushFileNote()) return;
    if (!contextMatches(context)) return;
    const data = await callBackend("setRepairAcceptanceB", fileId, JSON.stringify(payload));
    Object.assign(file, data);
    if (contextMatches(context)) {
      state.document.repairs_accepted = data.repairs_accepted;
      state.document.repair_accepted_at = data.repair_accepted_at;
    }
    setSaveState(accepted ? "Přijetí oprav uloženo" : "Přijetí oprav zrušeno", false);
  } catch (error) { showToast(error.message, true); }
  finally { state.reviewBusy = false; renderFileList(); }
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

function saveUiOptions(patch) {
  state.ui = { ...state.ui, ...patch };
  const prior = state.uiSavePending;
  state.uiSavePending = { contextId: state.contextId,
    patch: { ...(prior?.contextId === state.contextId ? prior.patch : {}), ...patch } };
  window.clearTimeout(state.uiSaveTimer);
  state.uiSaveTimer = window.setTimeout(flushUiOptions, 220);
}

function flushUiOptions() {
  window.clearTimeout(state.uiSaveTimer);
  const job = state.uiSaveQueue.then(async () => {
    while (state.uiSavePending) {
      const pending = state.uiSavePending;
      state.uiSavePending = null;
      if (pending.contextId !== state.contextId) continue;
      try { await callBackend("setUiOptionsB", JSON.stringify(pending.patch)); }
      catch (error) {
        if (pending.contextId === state.contextId) {
          const newer = state.uiSavePending;
          state.uiSavePending = { contextId: pending.contextId,
            patch: { ...pending.patch, ...(newer?.contextId === pending.contextId ? newer.patch : {}) } };
        }
        showToast(error.message, true);
        return false;
      }
    }
    return true;
  });
  state.uiSaveQueue = job.catch(() => false);
  return job;
}

function releasePageResources() {
  state.markingDrag?.cleanup();
  state.scanPan?.cleanup();
  window.clearTimeout(state.zoomRenderTimer);
  state.scanViews.clear();
  if (state.observer) state.observer.disconnect();
  window.clearTimeout(state.savePositionTimer);
  for (const url of state.objectUrls.values()) URL.revokeObjectURL(url);
  state.objectUrls.clear();
  state.pageData.clear();
  state.pendingRequests.clear();
  state.renderQueue.clear();
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

async function moveDocument(direction) {
  const candidates = filteredFiles();
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
  if (elements.moreActionsId.open) {
    if (event.key === "Escape") {
      elements.moreActionsId.open = false;
      elements.moreActionsId.querySelector("summary").focus();
      event.preventDefault();
    }
    return;
  }
  if (document.querySelector("dialog[open]")) return;
  if (event.key === "Escape") {
    setMarking(false);
    if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) target.blur();
    return;
  }
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return;
  if (handleIssueKeyboard(event)) return;
  if (event.key.toLowerCase() === "f" && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault(); setScanZoom(100); return;
  }
  if (event.key === "ArrowDown") { event.preventDefault(); moveDocument(1); }
  else if (event.key === "ArrowUp") { event.preventDefault(); moveDocument(-1); }
  else if (event.key === "PageDown") { event.preventDefault(); movePage(1); }
  else if (event.key === "PageUp") { event.preventDefault(); movePage(-1); }
  else if (event.code === "Space") {
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
  elements.zoomId.addEventListener("input", () => setScanZoom(Number(elements.zoomId.value)));
  elements.zoomId.addEventListener("change", () => setScanZoom(Number(elements.zoomId.value)));
  elements.zoomValueId.addEventListener("click", () => setScanZoom(100));
  elements.nameFilterId.addEventListener("input", () => {
    renderFileList();
    saveUiOptions({ name_filter: elements.nameFilterId.value });
  });
  elements.statusFilterId.addEventListener("change", () => {
    renderFileList();
    saveUiOptions({ review_filter: elements.statusFilterId.value });
  });
  elements.fileIssueFilterId.addEventListener("change", () => {
    renderFileList();
    saveUiOptions({ issue_filter: elements.fileIssueFilterId.value });
  });
  elements.fileNoteId.addEventListener("input", scheduleSaveNote);
  elements.pageScrollId.addEventListener("scroll", scheduleSaveCurrentPage, { passive: true });
  elements.moreActionsId.addEventListener("click", (event) => {
    if (event.target.closest("button")) elements.moreActionsId.open = false;
  });
  document.addEventListener("pointerdown", (event) => {
    if (!elements.moreActionsId.contains(event.target)) elements.moreActionsId.open = false;
  });
  elements.moreActionsId.addEventListener("focusout", (event) => {
    if (!elements.moreActionsId.contains(event.relatedTarget)) elements.moreActionsId.open = false;
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

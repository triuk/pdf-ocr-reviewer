"use strict";

const state = {
  folder: null,
  files: [],
  ui: {
    last_file: null,
    zoom_percent: 100,
    ocr_mode: "layout",
    overlay: false,
    status_filter: "all",
    name_filter: "",
    auto_advance: true,
  },
  activeFileId: null,
  document: null,
  pageData: new Map(),
  objectUrls: new Map(),
  pendingRequests: new Map(),
  generation: 0,
  applyingState: false,
  observer: null,
  visiblePages: new Set(),
  savePositionTimer: null,
  saveNoteTimer: null,
};

const elements = {};

function bindElements() {
  const ids = [
    "selectFolderId", "folderPathId", "openPathId", "refreshFolderId", "exportCsvId", "saveStateId",
    "ocrModeId", "overlayId", "zoomId", "zoomValueId", "nameFilterId",
    "statusFilterId", "fileSummaryId", "fileListId", "documentNameId",
    "documentMetaId", "pageScrollId", "emptyStateId", "pagesId",
    "fileNoteId", "toastId",
  ];
  for (const id of ids) elements[id] = document.getElementById(id);
}

function parseEnvelope(raw) {
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object" || typeof value.ok !== "boolean") {
    throw new Error("Backend returned an invalid response.");
  }
  if (!value.ok) {
    const error = new Error(value.error?.message || "Backend operation failed.");
    error.code = value.error?.code || "UNKNOWN_ERROR";
    if (error.code.endsWith("SAVE_FAILED")) setSaveState(error.message, true);
    throw error;
  }
  return value.data;
}

function showToast(message, isError = false) {
  elements.toastId.textContent = message;
  elements.toastId.classList.toggle("error", isError);
  elements.toastId.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toastId.classList.remove("visible"), 3500);
}

async function callBackend(name, ...args) {
  if (typeof webui === "undefined" || !webui.isConnected()) {
    throw new Error("Spojení s backendem není dostupné.");
  }
  const fn = webui[name];
  if (typeof fn !== "function") throw new Error(`Backend function ${name} is unavailable.`);
  return parseEnvelope(await fn(...args));
}

async function syncStateF() {
  const data = await callBackend("syncStateB");
  applyPublicState(data);
  if (data.startup_error) showToast(data.startup_error.message, true);
  if (data.persistence_error) setSaveState(data.persistence_error.message, true);
  else if (data.folder) setSaveState("Manifest je zapisovatelný", false);
  if (state.ui.last_file && state.files.some((file) => file.file_id === state.ui.last_file)) {
    await openDocumentF(state.ui.last_file);
  }
}

function applyPublicState(data) {
  state.applyingState = true;
  try {
    state.folder = data.folder;
    state.files = Array.isArray(data.files) ? data.files : [];
    state.ui = { ...state.ui, ...(data.ui || {}) };
    elements.folderPathId.value = state.folder || "";
    elements.ocrModeId.value = state.ui.ocr_mode;
    elements.overlayId.checked = Boolean(state.ui.overlay);
    elements.zoomId.value = state.ui.zoom_percent;
    elements.zoomValueId.value = `${state.ui.zoom_percent} %`;
    applyZoom(false);
    elements.nameFilterId.value = state.ui.name_filter || "";
    elements.statusFilterId.value = state.ui.status_filter || "all";
    renderFileList();
  } finally {
    state.applyingState = false;
  }
}


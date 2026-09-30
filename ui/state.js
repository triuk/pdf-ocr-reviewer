"use strict";

const state = {
  folder: null,
  contextId: null,
  navigationQueue: Promise.resolve(),
  navigating: false,
  files: [],
  ui: {
    last_file: null,
    zoom_percent: 100,
    ocr_mode: "pdf_order",
    overlay: true,
    status_filter: "all",
    review_filter: "all",
    name_filter: "",
    auto_advance: true,
    issue_kind: "position",
    issue_filter: "all",
  },
  activeFileId: null,
  document: null,
  pageData: new Map(),
  objectUrls: new Map(),
  pendingRequests: new Map(),
  generation: 0,
  renderGeneration: 0,
  applyingState: false,
  observer: null,
  visiblePages: new Set(),
  savePositionTimer: null,
  saveNoteTimer: null,
  fileNoteDraft: null,
  fileNoteQueue: Promise.resolve(),
  marking: false,
  issueKind: "position",
  selectedIssueId: null,
  issueFilter: "active",
  issueDrafts: new Map(),
  issueSaveTimer: null,
  issueQueue: Promise.resolve(),
  issueBusy: false,
  reviewBusy: false,
  draftRecords: new Map(),
  journalQueue: Promise.resolve(),
  journalPending: 0,
};

const elements = {};

function bindElements() {
  const ids = [
    "selectFolderId", "folderPathId", "openPathId", "refreshFolderId", "exportCsvId", "saveStateId", "moreActionsId",
    "ocrModeId", "overlayId", "zoomId", "zoomValueId", "nameFilterId",
    "statusFilterId", "fileIssueFilterId", "fileSummaryId", "fileListId", "documentNameId",
    "documentMetaId", "pageScrollId", "emptyStateId", "pagesId",
    "fileNoteId", "toastId",
    "issueSidebarId", "issueFilterId", "issueSummaryId", "issueListId",
    "markIssueId", "issueKindId", "previousIssueId", "nextIssueId", "markHintId",
    "issueEditorId", "selectedIssueTitleId", "selectedIssueKindId", "issueNoteId",
    "issueResultId", "reopenIssueId", "closeIssueId",
    "issueSaveId", "retryIssueSaveId", "draftRecoveryId", "draftRecoveryListId", "draftRecoverySummaryId",
    "backupsId", "backupDialogId", "backupSelectId", "restoreBackupId", "closeBackupsId", "backupDescriptionId",
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
    throw new Error("The backend connection is unavailable.");
  }
  const fn = webui[name];
  if (typeof fn !== "function") throw new Error(`Backend function ${name} is unavailable.`);
  const context = captureContext();
  const contextual = !["syncStateB", "saveDraftB", "deleteDraftB", "listBackupsB", "restoreBackupB"].includes(name);
  const documentBound = ["requestPageB", "setFileStatusB", "toggleProblemPageB", "setLastPageB", "setFileNoteB", "addIssueB", "updateIssueB"].includes(name);
  if (contextual) args.push(JSON.stringify({context_id: context.contextId, document_id: context.documentId}));
  const result = parseEnvelope(await fn(...args));
  if (contextual && (context.contextId !== state.contextId || (documentBound && !contextMatches(context)))) {
    throw new Error("Odpověď patří dříve otevřenému dokumentu; aktuální zobrazení se nezměnilo.");
  }
  return result;
}

function captureContext() {
  return {contextId: state.contextId, documentId: state.document?.document_id, fileId: state.activeFileId, generation: state.generation};
}

function contextMatches(context) {
  return context.contextId === state.contextId && context.documentId === state.document?.document_id
    && context.fileId === state.activeFileId && context.generation === state.generation;
}

function enqueueNavigation(work) {
  const job = state.navigationQueue.then(async () => {
    state.navigating = true;
    document.querySelectorAll(".file-ok input").forEach(input => { input.disabled = true; });
    document.querySelectorAll(".workspace, .issue-sidebar").forEach(node => { node.inert = true; });
    try { return await work(); }
    finally {
      state.navigating = false;
      document.querySelectorAll(".file-ok input").forEach(input => { input.disabled = state.reviewBusy; });
      document.querySelectorAll(".workspace, .issue-sidebar").forEach(node => { node.inert = false; });
      for (const index of state.visiblePages) requestPage(index);
    }
  });
  state.navigationQueue = job.catch(error => { showToast(error.message, true); return false; });
  return state.navigationQueue;
}

async function syncStateF() {
  const data = await callBackend("syncStateB");
  applyPublicState(data);
  if (data.startup_error) showToast(data.startup_error.message, true);
  if (data.persistence_error) setSaveState(data.persistence_error.message, true);
  else if (data.folder) setSaveState("Manifest lze ukládat", false);
  if (state.ui.last_file && state.files.some((file) => file.file_id === state.ui.last_file)) {
    await openDocumentF(state.ui.last_file);
  }
}

function applyPublicState(data) {
  state.applyingState = true;
  try {
    state.folder = data.folder;
    state.contextId = data.context_id;
    state.files = Array.isArray(data.files) ? data.files : [];
    state.ui = { ...state.ui, ...(data.ui || {}) };
    elements.folderPathId.value = state.folder || "";
    elements.ocrModeId.value = state.ui.ocr_mode;
    elements.overlayId.checked = Boolean(state.ui.overlay);
    elements.zoomId.value = state.ui.zoom_percent;
    elements.zoomValueId.value = `${state.ui.zoom_percent} %`;
    applyZoom(false);
    elements.nameFilterId.value = state.ui.name_filter || "";
    elements.statusFilterId.value = state.ui.review_filter || "all";
    elements.fileIssueFilterId.value = state.ui.issue_filter || "all";
    state.issueKind = state.ui.issue_kind || "position";
    elements.issueKindId.value = state.issueKind;
    renderFileList();
    absorbDrafts(data);
  } finally {
    state.applyingState = false;
  }
}

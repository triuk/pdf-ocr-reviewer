function openDocumentF(fileId, afterReload = false) {
  return enqueueNavigation(() => openDocumentNow(fileId, afterReload));
}

async function openDocumentNow(fileId, afterReload = false) {
  try {
    if (!await flushIssueDraft()) return;
    if (!afterReload && !await flushFileNote()) return;
    const generation = ++state.generation;
    state.pendingRequests.clear();

    const documentData = await callBackend("openDocumentB", fileId);
    if (generation !== state.generation) return;
    releasePageResources();
    state.activeFileId = fileId;
    state.document = documentData;
    restoreDocumentDrafts();
    state.selectedIssueId = null;
    if (documentData.persistence_error) setSaveState(documentData.persistence_error.message, true);
    else setSaveState("Manifest lze ukládat", false);
    state.pageData.clear();
    renderFileList();
    renderDocumentShell();
    elements.fileNoteId.value = documentData.note || "";
    if (state.fileNoteDraft?.fileId === fileId && state.fileNoteDraft.folder === state.folder) {
      elements.fileNoteId.value = state.fileNoteDraft.note;
      setSaveState("Poznámka souboru není uložena; zůstala v editoru", true);
    }
    const file = state.files.find((item) => item.file_id === fileId);
    if (file) { file.issue_counts = documentData.issue_counts; file.status = documentData.status; file.review_complete = documentData.review_complete; }
    renderFileList();
    refreshIssueViews();
    renderDraftRecovery();

    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (generation === state.generation) scrollToSavedPage(documentData.last_page || 0);
    return true;
  } catch (error) {
    showToast(error.message, true);
    return false;
  }
}

function clearDocument() {
  state.generation += 1;
  releasePageResources();
  state.activeFileId = null;
  state.document = null;
  state.selectedIssueId = null;
  elements.documentNameId.textContent = "Vyberte PDF";
  elements.documentMetaId.textContent = "";
  elements.pagesId.replaceChildren();
  elements.emptyStateId.hidden = false;
  elements.fileNoteId.value = "";
  elements.pageScrollId.scrollTop = 0;
  refreshIssueViews();
}

function renderDocumentShell() {
  const doc = state.document;
  elements.pageScrollId.scrollTop = 0;
  elements.documentNameId.textContent = doc.name;
  elements.documentMetaId.textContent = `${doc.page_count} stran`;
  elements.emptyStateId.hidden = true;
  elements.pagesId.replaceChildren();

  for (const page of doc.pages) {
    const row = document.createElement("article");
    row.className = "page-row";
    row.dataset.pageIndex = String(page.page_index);
    row.style.setProperty("--page-ratio", `${page.width} / ${page.height}`);

    const label = document.createElement("div");
    label.className = "page-label";
    const pageText = document.createElement("span");
    pageText.textContent = `Str. ${page.page_index + 1}`;
    const problemButton = document.createElement("button");
    problemButton.type = "button";
    problemButton.className = "problem-page-button";
    problemButton.textContent = "Chyba";
    problemButton.classList.toggle("active", doc.problem_pages.includes(page.page_index));
    problemButton.addEventListener("click", () => toggleProblemPageF(page.page_index, problemButton));
    label.append(pageText, problemButton);

    const scanPane = createPagePane("scan-pane", page);
    const ocrPane = createPagePane("ocr-pane", page);
    row.append(label, scanPane, ocrPane);
    elements.pagesId.append(row);
  }
  setupObserver();
}

function createPagePane(className, page) {
  const pane = document.createElement("div");
  pane.className = `page-pane ${className}`;
  pane.style.aspectRatio = `${page.width} / ${page.height}`;
  const placeholder = document.createElement("div");
  placeholder.className = "page-placeholder";
  placeholder.textContent = "Loading when nearby…";
  pane.append(placeholder);
  return pane;
}

function setupObserver() {
  if (state.observer) state.observer.disconnect();
  state.visiblePages.clear();

  state.observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const pageIndex = Number(entry.target.dataset.pageIndex);
      if (entry.isIntersecting) {
        state.visiblePages.add(pageIndex);
        requestPage(pageIndex);
      } else {
        state.visiblePages.delete(pageIndex);
      }
    }
    pruneLoadedPages();
  }, {
    root: elements.pageScrollId,
    rootMargin: "75% 0px 75% 0px",
    threshold: 0.01,
  });

  elements.pagesId.querySelectorAll(".page-row").forEach((row) => state.observer.observe(row));
}

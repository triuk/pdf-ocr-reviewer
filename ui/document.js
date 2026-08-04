async function openDocumentF(fileId) {
  try {
    state.generation += 1;
    releasePageResources();
    const documentData = await callBackend("openDocumentB", fileId);
    state.activeFileId = fileId;
    state.document = documentData;
    if (documentData.persistence_error) setSaveState(documentData.persistence_error.message, true);
    else setSaveState("Manifest je zapisovatelný", false);
    state.pageData.clear();
    renderFileList();
    renderDocumentShell();
    setActiveStatus(documentData.status);
    elements.fileNoteId.value = documentData.note || "";
    requestAnimationFrame(() => scrollToSavedPage(documentData.last_page || 0));
  } catch (error) {
    showToast(error.message, true);
  }
}

function clearDocument() {
  releasePageResources();
  state.activeFileId = null;
  state.document = null;
  elements.documentNameId.textContent = "Vyberte PDF";
  elements.documentMetaId.textContent = "";
  elements.pagesId.replaceChildren();
  elements.emptyStateId.hidden = false;
  elements.fileNoteId.value = "";
}

function renderDocumentShell() {
  const doc = state.document;
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
    pageText.textContent = `Strana ${page.page_index + 1}`;
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
  placeholder.textContent = "Načítání při přiblížení…";
  pane.append(placeholder);
  return pane;
}

function setupObserver() {
  if (state.observer) state.observer.disconnect();
  state.observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const pageIndex = Number(entry.target.dataset.pageIndex);
      if (entry.isIntersecting) {
        state.visiblePages.add(pageIndex);
        requestPage(pageIndex);
        scheduleSavePosition(pageIndex);
      } else {
        state.visiblePages.delete(pageIndex);
      }
    }
    pruneLoadedPages();
  }, { root: elements.pageScrollId, rootMargin: "120% 0px 120% 0px", threshold: 0.01 });
  document.querySelectorAll(".page-row").forEach((row) => state.observer.observe(row));
}


function filteredFiles() {
  const nameFilter = elements.nameFilterId.value.trim().toLocaleLowerCase("cs");
  const statusFilter = elements.statusFilterId.value;
  const issueFilter = elements.fileIssueFilterId?.value || "all";
  return state.files.filter((file) => {
    const nameMatch = !nameFilter || file.name.toLocaleLowerCase("cs").includes(nameFilter);
    const statusMatch = statusFilter === "all" || (statusFilter === "reviewed" ? file.review_complete : !file.review_complete);
    const count = issueFilter === "active"
      ? (file.issue_counts?.open || 0) + (file.issue_counts?.fixed || 0)
      : (file.issue_counts?.[issueFilter] || 0);
    const issueMatch = issueFilter === "all" || count > 0;
    return nameMatch && statusMatch && issueMatch;
  });
}

function renderFileList() {
  const visible = filteredFiles();
  elements.fileListId.replaceChildren();
  for (const file of visible) {
    const row = document.createElement("div");
    row.className = "file-item";
    row.dataset.fileId = file.file_id;
    row.classList.toggle("selected", file.file_id === state.activeFileId);
    row.setAttribute("role", "listitem");

    const ok = document.createElement("label");
    ok.className = "file-ok";
    ok.title = "OK — prohlídka PDF dokončena; připomínky mohou zůstat k opravě";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(file.review_complete);
    checkbox.disabled = state.reviewBusy || state.navigating;
    checkbox.setAttribute("aria-label", `OK: ${file.name}`);
    checkbox.addEventListener("change", () => setReviewCompleteF(checkbox.checked, file.file_id));
    const okText = document.createElement("span");
    okText.textContent = "OK";
    ok.append(checkbox, okText);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "file-open";
    button.setAttribute("aria-current", file.file_id === state.activeFileId ? "true" : "false");
    const name = document.createElement("span");
    name.className = "file-item-name";
    name.textContent = file.name;
    name.title = file.name;

    const meta = document.createElement("span");
    meta.className = "file-item-meta";
    const parts = [];
    if (file.problem_page_count) parts.push(`!${file.problem_page_count}`);
    if (file.changed_since_review) parts.push("změněno");
    meta.textContent = parts.join(" ");
    if (file.changed_since_review) meta.classList.add("file-changed");

    button.append(name, meta);
    const counts = file.issue_counts || {};
    if (counts.open || counts.fixed) {
      const summary = document.createElement("span");
      summary.className = "file-issue-summary";
      for (const [key, label] of [["open", "k opravě"], ["fixed", "po opravě"]]) {
        if (!counts[key]) continue;
        const part = document.createElement("span");
        part.className = `issue-${key}`;
        part.textContent = `${issueSymbols[key]} ${counts[key]} ${label}`;
        summary.append(part);
      }
      button.append(summary);
    }
    button.addEventListener("click", () => openDocumentF(file.file_id));
    row.append(ok, button);
    elements.fileListId.append(row);
  }

  const completed = state.files.filter(file => file.review_complete).length;
  elements.fileSummaryId.textContent = state.folder
    ? `${visible.length} / ${state.files.length} PDF · OK ${completed} z ${state.files.length}`
    : "Není otevřená složka.";
}

function setSaveState(message, isError) {
  elements.saveStateId.textContent = message;
  elements.saveStateId.title = message;
  elements.saveStateId.classList.toggle("error", isError);
}

async function exportCsvF() {
  try {
    const data = await callBackend("exportCsvB");
    const csvText = data.csv;
    const suggestedName = "pdf-ocr-reviewer-review.csv";
    if ("showSaveFilePicker" in window) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(csvText);
        await writable.close();
        showToast("CSV was saved.");
        return;
      } catch (error) {
        if (error?.name === "AbortError") return;
      }
    }
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = suggestedName;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    showToast(error.message, true);
  }
}

function selectFolderF() { return enqueueNavigation(selectFolderFNow); }

async function selectFolderFNow() {
  try {
    if (!await flushIssueDraft()) return;
    if (!await flushFileNote()) return;
    const data = await callBackend("selectFolderB");
    if (!data.cancelled) {
      clearDocument();
      applyPublicState(data);
      await openInitialDocumentAfterFolder();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

function openPathF() { return enqueueNavigation(openPathFNow); }

async function openPathFNow() {
  const path = elements.folderPathId.value.trim();
  if (!path) return;
  try {
    if (!await flushIssueDraft()) return;
    if (!await flushFileNote()) return;
    const data = await callBackend("openFolderB", path);
    clearDocument();
    applyPublicState(data);
    await openInitialDocumentAfterFolder();
  } catch (error) {
    showToast(error.message, true);
  }
}

function refreshFolderF() { return enqueueNavigation(refreshFolderFNow); }

async function refreshFolderFNow() {
  try {
    const fileId = state.activeFileId;
    const issueId = state.selectedIssueId;
    const pageIndex = getCurrentPageIndex();
    await flushIssueDraft(); // Failed drafts stay in memory; reloading must remain possible after a conflict.
    await flushFileNote();
    await state.issueQueue;
    window.clearTimeout(state.saveNoteTimer);
    window.clearTimeout(state.savePositionTimer);
    const data = await callBackend("refreshFolderB");
    state.selectedIssueId = null;
    clearDocument();
    applyPublicState(data);
    if (fileId && state.files.some((file) => file.file_id === fileId)) {
      if (!await openDocumentNow(fileId, true)) return;
      scrollToSavedPage(pageIndex);
      if (state.document?.issues.some((issue) => issue.id === issueId)) await selectIssue(issueId);
    } else {
      await openInitialDocumentAfterFolder();
    }
    showToast("Manifest i PDF znovu načteny.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openInitialDocumentAfterFolder() {
  if (state.ui.last_file && state.files.some((file) => file.file_id === state.ui.last_file)) {
    await openDocumentNow(state.ui.last_file);
  } else if (state.files.length) {
    await openDocumentNow(state.files[0].file_id);
  } else {
    clearDocument();
  }
}

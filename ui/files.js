function renderFileList() {
  const nameFilter = elements.nameFilterId.value.trim().toLocaleLowerCase("cs");
  const statusFilter = elements.statusFilterId.value;
  const visible = state.files.filter((file) => {
    const nameMatch = !nameFilter || file.name.toLocaleLowerCase("cs").includes(nameFilter);
    const statusMatch = statusFilter === "all" || file.status === statusFilter;
    return nameMatch && statusMatch;
  });

  elements.fileListId.replaceChildren();
  for (const file of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "file-item";
    button.dataset.fileId = file.file_id;
    button.classList.toggle("selected", file.file_id === state.activeFileId);
    button.setAttribute("role", "option");

    const status = document.createElement("span");
    status.className = `file-status ${file.status}`;
    status.textContent = statusSymbol(file.status);

    const name = document.createElement("span");
    name.className = "file-item-name";
    name.textContent = file.name;
    name.title = file.name;

    const meta = document.createElement("span");
    meta.className = "file-item-meta";
    const parts = [];
    if (file.problem_page_count) parts.push(`!${file.problem_page_count}`);
    if (file.changed_since_review) parts.push("změněn");
    meta.textContent = parts.join(" ");
    if (file.changed_since_review) meta.classList.add("file-changed");

    button.append(status, name, meta);
    button.addEventListener("click", () => openDocumentF(file.file_id));
    elements.fileListId.append(button);
  }

  const counts = Object.fromEntries(["unreviewed", "ok", "error", "needs_review"].map((key) => [key, 0]));
  for (const file of state.files) counts[file.status] = (counts[file.status] || 0) + 1;
  elements.fileSummaryId.textContent = state.folder
    ? `${state.files.length} PDF · ${counts.unreviewed} nezkontrolováno · ${counts.error} chyb`
    : "Žádná složka není otevřena.";
}

function statusSymbol(status) {
  return { unreviewed: "○", ok: "✓", error: "!", needs_review: "?" }[status] || "○";
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
        showToast("CSV bylo uloženo.");
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

async function selectFolderF() {
  try {
    const data = await callBackend("selectFolderB");
    if (!data.cancelled) {
      applyPublicState(data);
      await openInitialDocumentAfterFolder();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openPathF() {
  const path = elements.folderPathId.value.trim();
  if (!path) return;
  try {
    const data = await callBackend("openFolderB", path);
    applyPublicState(data);
    await openInitialDocumentAfterFolder();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshFolderF() {
  try {
    const data = await callBackend("refreshFolderB");
    applyPublicState(data);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openInitialDocumentAfterFolder() {
  if (state.ui.last_file && state.files.some((file) => file.file_id === state.ui.last_file)) {
    await openDocumentF(state.ui.last_file);
  } else if (state.files.length) {
    await openDocumentF(state.files[0].file_id);
  } else {
    clearDocument();
  }
}


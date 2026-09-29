"use strict";

const issueKindLabels = { position: "Špatná poloha", oversized: "Špatná velikost boxu", text: "Chybný text", missing: "Chybějící text", other: "Jiný problém" };
const issueStatusLabels = { open: "K opravě", fixed: "Po opravě", verified: "Dříve potvrzeno", dismissed: "Smazáno" };
const issueSymbols = { open: "!", fixed: "◉", verified: "✓", dismissed: "×" };

function selectedIssue() {
  return state.document?.issues?.find((issue) => issue.id === state.selectedIssueId);
}

function filteredIssues() {
  return (state.document?.issues || []).filter((issue) => {
    if (state.issueFilter === "all") return true;
    if (state.issueFilter === "archived") return ["dismissed", "verified"].includes(issue.status);
    if (state.issueFilter === "active") return ["open", "fixed"].includes(issue.status);
    return issue.status === state.issueFilter;
  }).sort((a, b) => a.page_index - b.page_index || a.bbox[1] - b.bbox[1] || a.bbox[0] - b.bbox[0]);
}

function draftKey(fileId, issueId) { return JSON.stringify([state.folder, fileId, issueId]); }

function issueSummaryText(counts) {
  return `${(counts.open || 0) + (counts.fixed || 0)} ponechaných · ${counts.fixed || 0} po opravě`;
}

function renderIssueSidebar() {
  elements.issueSidebarId.hidden = !state.document;
  elements.issueSummaryId.textContent = issueSummaryText(state.document?.issue_counts || {});
  elements.issueListId.replaceChildren();
  const issues = filteredIssues();
  elements.previousIssueId.disabled = !issues.length;
  elements.nextIssueId.disabled = !issues.length;
  elements.markIssueId.disabled = !state.document;
  elements.issueKindId.disabled = !state.document;
  for (const issue of issues) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `issue-list-item issue-${issue.status}`;
    button.classList.toggle("selected", issue.id === state.selectedIssueId);
    button.setAttribute("aria-pressed", String(issue.id === state.selectedIssueId));
    const heading = document.createElement("strong");
    heading.textContent = `${issueSymbols[issue.status]} ${issueStatusLabels[issue.status]} · str. ${issue.page_index + 1}`;
    const detail = document.createElement("span");
    detail.textContent = `${issueKindLabels[issue.kind]}${issue.text ? ` · ${issue.text}` : ""}`;
    button.title = `${heading.textContent}\n${detail.textContent}\n${issue.note}${(issue.stale || issue.invalid_target) ? "\nJiná verze PDF — nutné nové označení" : ""}`;
    if ((issue.stale || issue.invalid_target)) heading.textContent += " · jiná verze";
    button.append(heading, detail);
    button.addEventListener("click", () => selectIssue(issue.id));
    elements.issueListId.append(button);
  }
  if (!issues.length) {
    const empty = document.createElement("p");
    empty.className = "issue-empty";
    empty.textContent = "V tomto filtru nejsou připomínky.";
    elements.issueListId.append(empty);
  }
}

function renderIssueEditor() {
  const issue = selectedIssue();
  elements.issueEditorId.hidden = !issue;
  document.querySelector(".note-panel").classList.toggle("has-issue", Boolean(issue));
  if (!issue) return;
  elements.selectedIssueTitleId.className = `issue-${issue.status}`;
  elements.selectedIssueTitleId.textContent = `${issueSymbols[issue.status]} ${issueStatusLabels[issue.status]} · strana ${issue.page_index + 1}`;
  const draft = state.issueDrafts.get(draftKey(state.activeFileId, issue.id));
  elements.selectedIssueKindId.value = draft?.kind || issue.kind;
  elements.issueNoteId.value = draft?.note ?? issue.note;
  elements.issueSaveId.textContent = draft ? "Neuložené změny" : "Uloženo";
  elements.retryIssueSaveId.hidden = !draft;
  elements.reopenIssueId.hidden = !["dismissed", "verified"].includes(issue.status);
  elements.reopenIssueId.disabled = state.issueBusy;
  const result = issue.result ? `Poslední oprava: ${issue.result.summary}` : "";
  elements.issueResultId.textContent = (issue.stale || issue.invalid_target)
    ? `⚠ Označení patří k jiné verzi PDF. Znovu označte aktuální místo; toto můžete zrušit. ${result}`
    : result;
  elements.issueResultId.classList.toggle("stale", Boolean((issue.stale || issue.invalid_target)));
}

function positionIssueRect(element, bbox, width, height) {
  element.style.left = `${100 * bbox[0] / width}%`;
  element.style.top = `${100 * bbox[1] / height}%`;
  element.style.width = `${100 * (bbox[2] - bbox[0]) / width}%`;
  element.style.height = `${100 * (bbox[3] - bbox[1]) / height}%`;
}

function renderPageIssues(pageIndex) {
  const row = elements.pagesId.querySelector(`[data-page-index="${pageIndex}"]`);
  if (!row) return;
  row.querySelectorAll(".issue-annotations").forEach((layer) => layer.remove());
  const loaded = state.pageData.get(pageIndex);
  if (!loaded) return;
  const panes = [row.querySelector(".scan-pane")];
  if (state.ui.ocr_mode === "layout") panes.push(row.querySelector(".ocr-pane"));
  for (const pane of panes) {
    const layer = document.createElement("div");
    layer.className = "issue-annotations";
    for (const issue of state.document?.issues || []) {
      if (issue.page_index !== pageIndex || !["open", "fixed"].includes(issue.status)) continue;
      const box = document.createElement("div");
      box.className = `issue-box issue-${issue.status}`;
      box.dataset.issueId = issue.id;
      box.classList.toggle("selected", issue.id === state.selectedIssueId);
      box.classList.toggle("stale", (issue.stale || issue.invalid_target));
      // A stale region remains in its old relative position and is explicitly flagged.
      positionIssueRect(box, issue.bbox, issue.page_width, issue.page_height);
      box.title = `${issueStatusLabels[issue.status]} · ${issueKindLabels[issue.kind]}${issue.note ? `\n${issue.note}` : ""}${(issue.stale || issue.invalid_target) ? "\nJiná verze PDF" : ""}`;
      const controls = document.createElement("div");
      controls.className = "issue-box-controls";
      // Keep both controls accessible even on small boxes against a page edge.
      controls.style.right = `min(0px, calc(${100 * issue.bbox[2] / issue.page_width}cqw - 48px))`;
      controls.style.top = `max(-18px, -${100 * issue.bbox[1] / issue.page_height}cqh)`;
      const badge = document.createElement("button");
      badge.type = "button";
      badge.className = "issue-badge";
      badge.textContent = issueSymbols[issue.status];
      badge.setAttribute("aria-label", `${box.title}, strana ${pageIndex + 1}`);
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "issue-box-dismiss";
      dismiss.textContent = "×";
      dismiss.title = "Smazat označení — vyřadit z dalších oprav";
      dismiss.setAttribute("aria-label", `Smazat označení: ${issueKindLabels[issue.kind]}, strana ${pageIndex + 1}`);
      dismiss.addEventListener("pointerdown", (event) => {
        // Keep the note focused until its draft is flushed by the action itself.
        event.preventDefault();
        event.stopPropagation();
      });
      dismiss.addEventListener("click", (event) => {
        event.stopPropagation();
        changeIssueStatus("dismissed", issue.id);
      });
      controls.append(badge, dismiss);
      box.append(controls);
      box.addEventListener("click", (event) => {
        event.stopPropagation();
        selectIssue(issue.id, false);
      });
      layer.append(box);
    }
    pane.append(layer);
  }
}

function refreshIssueViews(includeEditor = true) {
  renderIssueSidebar();
  if (includeEditor) renderIssueEditor();
  renderDraftRecovery();
  for (const pageIndex of state.pageData.keys()) renderPageIssues(pageIndex);
}

async function selectIssue(issueId, scroll = true) {
  const context = captureContext();
  if (issueId !== state.selectedIssueId && !await flushIssueDraft()) return;
  if (!contextMatches(context)) return;
  state.selectedIssueId = issueId;
  refreshIssueViews();
  const issue = selectedIssue();
  if (issue && scroll) {
    const row = elements.pagesId.querySelector(`[data-page-index="${issue.page_index}"]`);
    await requestPage(issue.page_index);
    if (!contextMatches(context)) return;
    // Center the marked area, not just the page header, at any zoom.
    const pane = row?.querySelector(".scan-pane");
    if (pane) {
      const container = elements.pageScrollId;
      const center = ((issue.bbox[1] + issue.bbox[3]) / 2) / issue.page_height;
      container.scrollTo({ top: Math.max(0, container.scrollTop + pane.getBoundingClientRect().top
        - container.getBoundingClientRect().top + center * pane.clientHeight - container.clientHeight / 2), behavior: "smooth" });
    }
  }
}

async function navigateIssue(direction) {
  const issues = filteredIssues();
  if (!issues.length) return;
  const index = issues.findIndex((issue) => issue.id === state.selectedIssueId);
  const next = index < 0 ? (direction > 0 ? 0 : issues.length - 1) : (index + direction + issues.length) % issues.length;
  await selectIssue(issues[next].id);
}

function applyIssueResponse(data) {
  const file = state.files.find((item) => item.file_id === data.file_id);
  if (file) file.issue_counts = data.issue_counts;
  if (state.activeFileId === data.file_id && state.document) {
    Object.assign(state.document, { issues: data.issues, issue_counts: data.issue_counts });
  }
  renderFileList();
  setSaveState("Manifest uložen", false);
}

function queueIssueWork(work) {
  const context = captureContext();
  const job = state.issueQueue.then(() => {
    if (!contextMatches(context)) throw new Error("Dokument se změnil; rozpracovaná připomínka zůstala zachována.");
    return work();
  });
  state.issueQueue = job.catch(() => {});
  return job;
}

function scheduleIssueDraft() {
  const issue = selectedIssue();
  if (!issue) return;
  const previous = state.issueDrafts.get(draftKey(state.activeFileId, issue.id));
  const draft = { folder: state.folder, token: crypto.randomUUID(), base_revision: state.document.manifest_revision, base_note: previous?.base_note ?? issue.note, base_kind: previous?.base_kind ?? issue.kind, recovered: Boolean(previous?.recovered), fileId: state.activeFileId, issueId: issue.id, expected_sha256: state.document.ocr_sha256,
    note: elements.issueNoteId.value, kind: elements.selectedIssueKindId.value };
  const key = draftKey(draft.fileId, draft.issueId);
  state.issueDrafts.set(key, draft);
  persistDraft(draft);
  elements.issueSaveId.textContent = "Ukládání…";
  window.clearTimeout(state.issueSaveTimer);
  state.issueSaveTimer = window.setTimeout(() => saveIssueDraft(key), 450);
}

async function saveIssueDraft(key) {
  return queueIssueWork(async () => {
    while (state.issueDrafts.has(key)) {
      const draft = state.issueDrafts.get(key);
      if (draft.recovered) return true;
      await state.journalQueue;
      try {
        const data = await callBackend("updateIssueB", draft.fileId, draft.issueId, JSON.stringify({
          note: draft.note, kind: draft.kind, expected_sha256: draft.expected_sha256,
        }));
        if (state.issueDrafts.get(key) === draft) state.issueDrafts.delete(key);
        forgetDraft(draft);
        applyIssueResponse(data);
        refreshIssueViews(false);
        if (state.selectedIssueId === draft.issueId) {
          elements.issueSaveId.textContent = state.issueDrafts.has(key) ? "Ukládání…" : "Uloženo";
          elements.retryIssueSaveId.hidden = !state.issueDrafts.has(key);
        }
      } catch (error) {
        elements.issueSaveId.textContent = "Neuloženo — poznámka zůstává zde";
        elements.retryIssueSaveId.hidden = false;
        showToast(error.message, true);
        return false;
      }
    }
    return true;
  });
}

async function flushIssueDraft() {
  window.clearTimeout(state.issueSaveTimer);
  if (!state.activeFileId || !state.selectedIssueId) { await state.issueQueue; return true; }
  return saveIssueDraft(draftKey(state.activeFileId, state.selectedIssueId));
}

async function changeIssueStatus(status, issueId = state.selectedIssueId) {
  const issue = state.document?.issues.find((item) => item.id === issueId);
  if (!issue || state.issueBusy || state.navigating) return;
  const fileId = state.activeFileId;
  const hash = state.document.ocr_sha256;
  state.issueBusy = true;
  renderIssueEditor();
  try {
    if (!await flushIssueDraft()) return;
    const data = await queueIssueWork(() => callBackend("updateIssueB", fileId, issue.id, JSON.stringify({ status, expected_sha256: hash })));
    applyIssueResponse(data);
    if (state.activeFileId !== fileId) return;
    if (status === "dismissed" && state.selectedIssueId === issue.id) state.selectedIssueId = null;
    if (status === "open") {
      state.issueFilter = "active";
      elements.issueFilterId.value = "active";
    }
    showToast(status === "open" ? "Označení obnoveno pro další opravu. PDF se nemění." : "Označení smazáno. Obnovit jej můžete v Archivu.");
  } catch (error) { showToast(error.message, true); }
  finally { state.issueBusy = false; refreshIssueViews(); }
}

function setMarking(enabled) {
  state.marking = enabled;
  elements.pagesId.classList.toggle("marking", enabled);
  elements.markIssueId.setAttribute("aria-pressed", String(enabled));
  elements.markHintId.textContent = enabled
    ? "Klik = slovo · tažení = oblast · Shift + tažení = přes jiné označení · Esc = čtení"
    : "M: označit slovo kliknutím nebo oblast tažením. Esc: čtení.";
}

function bindRegionMarking(pane, pageIndex, ocr) {
  pane.markingAbortController?.abort();
  pane.markingAbortController = new AbortController();
  pane.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".issue-box-controls")) return;
    if (!state.marking || event.button !== 0 || (!event.shiftKey && event.target.closest(".issue-box"))) return;
    event.preventDefault();
    event.stopPropagation();
    const start = { x: event.clientX, y: event.clientY };
    const bounds = pane.getBoundingClientRect();
    const point = (e) => [Math.max(0, Math.min(ocr.page_width, (e.clientX - bounds.left) / bounds.width * ocr.page_width)),
      Math.max(0, Math.min(ocr.page_height, (e.clientY - bounds.top) / bounds.height * ocr.page_height))];
    const origin = point(event);
    const preview = document.createElement("div");
    preview.className = "issue-drag-preview";
    pane.append(preview);
    pane.setPointerCapture(event.pointerId);
    const controller = new AbortController();
    const options = { signal: controller.signal };
    const cleanup = () => {
      controller.abort(); preview.remove();
      if (pane.hasPointerCapture(event.pointerId)) pane.releasePointerCapture(event.pointerId);
    };
    const region = (end) => [Math.min(origin[0], end[0]), Math.min(origin[1], end[1]), Math.max(origin[0], end[0]), Math.max(origin[1], end[1])];
    pane.addEventListener("pointermove", (move) => positionIssueRect(preview, region(point(move)), ocr.page_width, ocr.page_height), options);
    pane.addEventListener("pointercancel", cleanup, options);
    pane.addEventListener("lostpointercapture", cleanup, options);
    document.addEventListener("keydown", (key) => { if (key.key === "Escape") cleanup(); }, options);
    pane.addEventListener("pointerup", (up) => {
      const end = point(up);
      let bbox = region(end);
      const dragged = Math.hypot(up.clientX - start.x, up.clientY - start.y) >= 5;
      if (!dragged) {
        const word = ocr.layout_items.filter((item) => origin[0] >= item.x0 && origin[0] <= item.x1 && origin[1] >= item.y0 && origin[1] <= item.y1)
          .sort((a, b) => (a.x1 - a.x0) * (a.y1 - a.y0) - (b.x1 - b.x0) * (b.y1 - b.y0))[0];
        if (!word) { cleanup(); showToast("Zde není OCR slovo. Označte místo tažením obdélníku."); return; }
        bbox = [Math.max(0, word.x0), Math.max(0, word.y0), Math.min(ocr.page_width, word.x1), Math.min(ocr.page_height, word.y1)];
      }
      cleanup();
      if (bbox[2] - bbox[0] < 0.2 || bbox[3] - bbox[1] < 0.2) return;
      createIssue(pageIndex, bbox);
    }, options);
  }, { capture: true, signal: pane.markingAbortController.signal });
}

async function createIssue(pageIndex, bbox) {
  if (state.navigating) return;
  if (!state.document) return;
  const fileId = state.activeFileId;
  const payload = { page_index: pageIndex, bbox, kind: state.issueKind, expected_sha256: state.document.ocr_sha256 };
  if (!await flushIssueDraft()) return;
  try {
    const data = await queueIssueWork(() => callBackend("addIssueB", fileId, JSON.stringify(payload)));
    applyIssueResponse(data);
    if (state.activeFileId !== fileId) return;
    state.selectedIssueId = data.issue_id;
    if (!["active", "all", "open"].includes(state.issueFilter)) {
      state.issueFilter = "active"; elements.issueFilterId.value = "active";
    }
    refreshIssueViews();
  } catch (error) { showToast(error.message, true); }
}

function attachIssueEvents() {
  elements.selectedIssueKindId.replaceChildren(...[...elements.issueKindId.options].map((option) => option.cloneNode(true)));
  elements.markIssueId.addEventListener("click", () => setMarking(!state.marking));
  const rememberKind = (kind) => {
    state.issueKind = kind;
    elements.issueKindId.value = kind;
    saveUiOptions({ issue_kind: kind });
  };
  elements.issueKindId.addEventListener("change", () => rememberKind(elements.issueKindId.value));
  elements.issueFilterId.addEventListener("change", () => { state.issueFilter = elements.issueFilterId.value; renderIssueSidebar(); });
  elements.previousIssueId.addEventListener("click", () => navigateIssue(-1));
  elements.nextIssueId.addEventListener("click", () => navigateIssue(1));
  elements.issueNoteId.addEventListener("input", scheduleIssueDraft);
  elements.issueNoteId.addEventListener("blur", flushIssueDraft);
  elements.selectedIssueKindId.addEventListener("change", () => {
    rememberKind(elements.selectedIssueKindId.value);
    scheduleIssueDraft();
  });
  elements.reopenIssueId.addEventListener("click", () => changeIssueStatus("open"));
  elements.retryIssueSaveId.addEventListener("click", () => {
    // An explicit retry after reload applies the retained note to the now-visible revision.
    const draft = state.issueDrafts.get(draftKey(state.activeFileId, state.selectedIssueId));
    if (draft && state.document) applyRecoveredDraft(draft);
  });
  elements.closeIssueId.addEventListener("click", () => selectIssue(null, false));
  window.addEventListener("beforeunload", (event) => {
    if (state.journalPending || [...state.draftRecords.values()].some(draft => !draft.durable)) { event.preventDefault(); event.returnValue = ""; }
  });
  renderIssueSidebar();
}

function handleIssueKeyboard(event) {
  if (event.ctrlKey || event.metaKey || event.altKey) return false;
  const key = event.key.toLowerCase();
  if (key === "m") setMarking(!state.marking);
  else if (key === "escape") setMarking(false);
  else if (key === "[" || key === "k") navigateIssue(-1);
  else if (key === "]" || key === "j") navigateIssue(1);
  else if (key === "n" && selectedIssue()) elements.issueNoteId.focus();
  else return false;
  event.preventDefault();
  return true;
}

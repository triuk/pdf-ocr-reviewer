"use strict";

function recoveryKey(draft) { return JSON.stringify([draft.folder, draft.fileId, draft.issueId || null]); }

function journalWork(work) {
  state.journalPending += 1;
  const job = state.journalQueue.then(work);
  state.journalQueue = job.catch(error => { showToast(error.message, true); }).finally(() => { state.journalPending -= 1; });
  return state.journalQueue;
}

function persistDraft(draft) {
  state.draftRecords.set(recoveryKey(draft), draft);
  if (draft.recovered) renderDraftRecovery();
  return journalWork(async () => {
    await callBackend("saveDraftB", JSON.stringify(draft));
    draft.durable = true;
  });
}

function forgetDraft(draft) {
  const key = recoveryKey(draft);
  if (state.draftRecords.get(key)?.token === draft.token) state.draftRecords.delete(key);
  return journalWork(() => callBackend("deleteDraftB", draft.token));
}

function absorbDrafts(data) {
  for (const draft of data.drafts || []) {
    const key = recoveryKey(draft);
    if (!state.draftRecords.has(key)) state.draftRecords.set(key, {...draft, durable: true, recovered: true});
  }
  if (data.draft_error) showToast(data.draft_error, true);
  renderDraftRecovery();
}

function restoreDocumentDrafts() {
  state.fileNoteDraft = null;
  for (const record of state.draftRecords.values()) {
    if (record.folder !== state.folder || record.fileId !== state.activeFileId) continue;
    const issue = record.issueId ? state.document.issues.find(i => i.id === record.issueId) : null;
    if (record.issueId && !issue) continue;
    const currentNote = issue ? issue.note : state.document.note;
    if (currentNote === record.note && (!issue || issue.kind === record.kind)) {
      forgetDraft(record); continue;
    }
    record.recovered = true; // Explicitly apply restored drafts; navigation can still proceed.
    if (issue) state.issueDrafts.set(draftKey(record.fileId, issue.id), record);
    else state.fileNoteDraft = record;
  }
}

function renderDraftRecovery() {
  if (!elements.draftRecoveryId) return;
  const records = [...state.draftRecords.values()].filter(d => d.folder === state.folder && d.recovered);
  elements.draftRecoveryId.hidden = !records.length;
  elements.draftRecoveryListId.replaceChildren();
  elements.draftRecoverySummaryId.textContent = `Obnovené poznámky (${records.length})`;
  for (const draft of records) {
    const row = document.createElement("div"); row.className = "recovery-row";
    const title = document.createElement("strong"); title.textContent = `${draft.fileId} · ${draft.issueId ? "poznámka k místu" : "poznámka souboru"}`;
    const text = document.createElement("textarea"); text.readOnly = true; text.rows = 2; text.value = draft.note; text.setAttribute("aria-label", "Obnovený text; lze zkopírovat");
    const current = document.createElement("p");
    const same = state.activeFileId === draft.fileId;
    const issue = same && draft.issueId ? state.document?.issues.find(i => i.id === draft.issueId) : null;
    current.textContent = same ? `V manifestu: ${draft.issueId ? (issue ? issue.note : "Připomínka již neexistuje; koncept můžete zkopírovat.") : state.document?.note || "(prázdné)"}` : "Otevřete PDF pro porovnání s uloženou poznámkou.";
    if (same && draft.expected_sha256 !== state.document?.ocr_sha256) current.textContent = "PDF má jinou verzi. " + current.textContent;
    const apply = document.createElement("button"); apply.type = "button"; apply.textContent = same ? "Použít koncept" : "Otevřít PDF";
    apply.disabled = !state.files.some(f => f.file_id === draft.fileId) || (same && Boolean(draft.issueId) && !issue);
    apply.addEventListener("click", async () => {
      if (!same) { await openDocumentF(draft.fileId); return; }
      await applyRecoveredDraft(draft);
    });
    const discard = document.createElement("button"); discard.type = "button"; discard.className = "secondary"; discard.textContent = "Ponechat uložené";
    discard.addEventListener("click", async () => {
      await forgetDraft(draft);
      if (state.fileNoteDraft?.token === draft.token) { state.fileNoteDraft = null; elements.fileNoteId.value = state.document?.note || ""; }
      const key = draftKey(draft.fileId, draft.issueId);
      if (state.issueDrafts.get(key)?.token === draft.token) state.issueDrafts.delete(key);
      refreshIssueViews(); renderDraftRecovery();
    });
    row.append(title, text, current, apply, discard); elements.draftRecoveryListId.append(row);
  }
}

async function applyRecoveredDraft(draft) {
  if (draft.folder !== state.folder || draft.fileId !== state.activeFileId || state.navigating) return;
  const issue = draft.issueId ? state.document.issues.find(i => i.id === draft.issueId) : null;
  if (draft.issueId && !issue) return;
  const replacement = {...draft, token: crypto.randomUUID(), recovered: false, durable: false,
    expected_sha256: state.document.ocr_sha256, base_note: issue ? issue.note : state.document.note,
    base_kind: issue?.kind};
  persistDraft(replacement);
  if (issue) {
    state.issueDrafts.set(draftKey(draft.fileId, draft.issueId), replacement);
    await saveIssueDraft(draftKey(draft.fileId, draft.issueId));
  } else {
    state.fileNoteDraft = replacement;
    elements.fileNoteId.value = replacement.note;
    await flushFileNote();
  }
  refreshIssueViews(); renderDraftRecovery();
}

async function showBackups() {
  try {
    const folder = elements.folderPathId.value.trim();
    if (!folder) throw new Error("Nejdříve vyberte složku nebo zadejte její cestu.");
    const data = await callBackend("listBackupsB", folder);
    state.backupSelection = data;
    elements.backupSelectId.replaceChildren();
    for (const backup of data.backups) {
      const option = document.createElement("option"); option.value = backup.id;
      option.textContent = `${backup.updated_at || backup.id} · ${backup.files} PDF · ${backup.issues} připomínek`;
      elements.backupSelectId.append(option);
    }
    elements.restoreBackupId.disabled = !data.backups.length;
    elements.backupDescriptionId.textContent = data.backups.length
      ? "Obnova nahradí manifest vybranou zálohou. Aktuální soubor se uchová jako before-restore.json; PDF se nemění."
      : "V této složce nejsou dostupné platné zálohy.";
    elements.backupDialogId.showModal();
  } catch (error) { showToast(error.message, true); }
}

function attachRecoveryEvents() {
  elements.backupsId.addEventListener("click", showBackups);
  elements.closeBackupsId.addEventListener("click", () => elements.backupDialogId.close());
  elements.restoreBackupId.addEventListener("click", () => enqueueNavigation(async () => {
    try {
      await state.journalQueue;
      const selection = state.backupSelection;
      const data = await callBackend("restoreBackupB", selection.folder, elements.backupSelectId.value, JSON.stringify(selection.revision));
      clearDocument(); applyPublicState(data); await openInitialDocumentAfterFolder();
      elements.backupDialogId.close(); showToast("Manifest obnoven ze zálohy.");
    } catch (error) { showToast(error.message, true); }
  }));
}

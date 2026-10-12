const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app}=require('./harness.cjs');

function placeholder(id, replacement_text='', extra={}) {
  return {id,origin:'ocr_placeholder',status:'open',replacement_text,page_index:0,bbox:[0,0,1,1],...extra};
}

test('transcription filters distinguish unanswered, supplied and archived regions',()=>{
  const c=app(['state.js','issues.js']);
  c.state.document.issues=[placeholder('empty'),placeholder('spaces','  '),placeholder('filled','í'),
    placeholder('gone','',{status:'dismissed'}),placeholder('stale','',{stale:true}),
    placeholder('fixed','x',{status:'fixed'}),{id:'manual',status:'open',page_index:0,bbox:[0,0,1,1]}];
  c.state.issueFilter='unreadable';
  assert.deepEqual(Array.from(c.filteredIssues(),i=>i.id),['empty','spaces']);
  c.state.issueFilter='transcribed';
  assert.deepEqual(Array.from(c.filteredIssues(),i=>i.id),['filled']);
});

test('next unanswered flushes supplied text, skips filled and wraps without resolving empty text',async()=>{
  const c=app(['state.js','issues.js']);
  c.state.document.issues=[placeholder('one'),placeholder('two'),placeholder('three','filled')];
  c.state.selectedIssueId='one';c.elements.issueFilterId={value:''};
  c.flushIssueDraft=async()=>{c.state.document.issues[0].replacement_text='a';return true;};
  c.selectIssue=async id=>{c.state.selectedIssueId=id;};
  await c.nextUnreadable();assert.equal(c.state.selectedIssueId,'two');
  await c.nextUnreadable();assert.equal(c.state.selectedIssueId,'two');
  assert.equal(c.state.document.issues[1].status,'open');
  c.flushIssueDraft=async()=>false;
  c.state.selectedIssueId='one';await c.nextUnreadable();assert.equal(c.state.selectedIssueId,'one');
});

test('autosave sends replacement independently of the note and retains it on failure',async()=>{
  const c=app(['state.js','issues.js']);
  c.state.folder='/a';c.state.document.issues=[placeholder('one')];c.state.selectedIssueId='one';
  c.elements.issueSaveId={};c.elements.retryIssueSaveId={};c.refreshIssueViews=()=>{};
  const key=c.draftKey('a.pdf','one');
  const draft={fileId:'a.pdf',issueId:'one',note:'context note',kind:'text',replacement_text:'í',expected_sha256:'sha'};
  c.state.issueDrafts.set(key,draft);
  c.callBackend=async()=>{throw Error('conflict');};
  assert.equal(await c.saveIssueDraft(key),false);
  assert.equal(c.state.issueDrafts.get(key).replacement_text,'í');
  let sent;
  c.callBackend=async(name,file,id,payload)=>{sent=JSON.parse(payload);return {file_id:file,issue:{...placeholder(id),...sent},issue_counts:{open:1}};};
  assert.equal(await c.saveIssueDraft(key),true);
  assert.equal(sent.replacement_text,'í');assert.equal(sent.note,'context note');
  assert.equal(c.state.issueDrafts.size,0);
});

test('recovery retains a replacement-only draft until explicitly applied',()=>{
  const c=app(['state.js','recovery.js']);
  c.draftKey=(file,id)=>JSON.stringify([c.state.folder,file,id]);c.state.folder='/a';
  c.state.document={issues:[{...placeholder('one'),note:'',kind:'text'}]};
  const record={folder:'/a',fileId:'a.pdf',issueId:'one',token:'1',note:'',kind:'text',replacement_text:'í'};
  c.state.draftRecords.set(c.recoveryKey(record),record);
  c.restoreDocumentDrafts();
  assert.equal(c.state.draftRecords.size,1);
  assert.equal(c.state.issueDrafts.get(c.draftKey('a.pdf','one')).replacement_text,'í');
  assert.equal(c.state.document.issues[0].replacement_text,'');
});

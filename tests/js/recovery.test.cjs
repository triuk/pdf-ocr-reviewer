const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app,deferred}=require('./harness.cjs');

test('restored drafts remain separate until explicit acceptance and missing targets are retained',()=>{
  const c=app(['state.js','recovery.js']);
  c.draftKey=(file,issue)=>JSON.stringify([c.state.folder,file,issue]);
  c.state.folder='/a';c.state.document={ocr_sha256:'new',note:'saved file note',issues:[{id:'i',note:'external note',kind:'text'}]};
  const issue={folder:'/a',fileId:'a.pdf',issueId:'i',note:'recovered',kind:'text',token:'1',expected_sha256:'old',base_note:'original'};
  const missing={...issue,issueId:'gone',token:'2'};
  c.state.draftRecords.set(c.recoveryKey(issue),issue);c.state.draftRecords.set(c.recoveryKey(missing),missing);
  c.restoreDocumentDrafts();
  assert.equal(c.state.document.issues[0].note,'external note');
  assert.equal(c.state.issueDrafts.get(c.draftKey('a.pdf','i')).note,'recovered');
  assert.equal(c.state.issueDrafts.get(c.draftKey('a.pdf','i')).recovered,true);
  assert.equal(c.state.draftRecords.size,2);
});

test('old save acknowledgement cannot delete a newer durable draft', async()=>{
  const c=app(['state.js','recovery.js']);const calls=[];
  c.callBackend=async(...args)=>calls.push(args);
  const old={folder:'/a',fileId:'a.pdf',token:'old',note:'old'};
  const newer={...old,token:'new',note:'new'};
  c.persistDraft(old);c.persistDraft(newer);await c.forgetDraft(old);
  assert.equal(c.state.draftRecords.get(c.recoveryKey(newer)).note,'new');
  assert.equal(newer.durable,true);assert.equal(c.state.journalPending,0);
  assert.deepEqual(calls.map(a=>a[0]),['saveDraftB','saveDraftB','deleteDraftB']);
  assert.equal(calls[2][1],'old');
});

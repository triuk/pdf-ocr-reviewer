const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {app,deferred}=require('./harness.cjs');
const ok = data=>JSON.stringify({ok:true,data});

test('late completion response cannot mark the newly opened PDF', async()=>{
  const c=app();const d=deferred();
  c.webui={isConnected:()=>true,setReviewCompleteB:()=>d.promise};
  c.state.files=[{file_id:'a.pdf',review_complete:false},{file_id:'b.pdf',review_complete:false}];
  const job=c.setReviewCompleteF(true);
  c.state.activeFileId='b.pdf';c.state.document={document_id:'doc-B',review_complete:false};
  d.resolve(ok({file_id:'a.pdf',review_complete:true}));await job;
  assert.equal(c.state.files[1].review_complete,false);assert.equal(c.state.document.review_complete,false);
  assert.equal(c.state.files[0].review_complete,true);
});

test('same name in another folder rejects an old response', async()=>{
  const c=app();const d=deferred();
  c.webui={isConnected:()=>true,setFileNoteB:()=>d.promise};
  const job=c.callBackend('setFileNoteB','a.pdf','old folder note');
  c.state.contextId='folder-B';d.resolve(ok({}));
  await assert.rejects(job,/dříve otevřenému/);
});

test('flush drains a newer note typed while the old note is saving',async()=>{
  const c=app();const d=deferred();const notes=[];
  c.state.folder='/a';c.state.fileNoteDraft={folder:'/a',fileId:'a.pdf',note:'first'};
  c.callBackend=async(name,file,note)=>{notes.push(note);if(note==='first') await d.promise;};
  const job=c.flushFileNote();await Promise.resolve();
  c.state.fileNoteDraft={folder:'/a',fileId:'a.pdf',note:'latest'};d.resolve();await job;
  assert.deepEqual(notes,['first','latest']);assert.equal(c.state.fileNoteDraft,null);
});

test('failed PDF open keeps the old document and loaded pages', async()=>{
  const c=app(['state.js','workflow.js','document.js']);
  c.flushIssueDraft=async()=>true;c.flushFileNote=async()=>true;c.callBackend=async()=>{throw Error('broken');};
  c.state.pageData.set(0,{old:true});c.elements.pageScrollId={scrollTop:123};
  let released=false;c.releasePageResources=()=>{released=true;};
  assert.equal(await c.openDocumentNow('broken.pdf'),false);
  assert.equal(c.state.activeFileId,'a.pdf');assert.equal(c.state.pageData.size,1);assert.equal(released,false);
});

test('navigation operations execute in order', async()=>{
  const c=app();const d=deferred();const started=deferred();const order=[];
  const a=c.enqueueNavigation(async()=>{order.push('a-start');started.resolve();await d.promise;order.push('a-end');});
  const b=c.enqueueNavigation(async()=>{order.push('b');});
  await started.promise;assert.deepEqual(order,['a-start']);d.resolve();await Promise.all([a,b]);
  assert.deepEqual(order,['a-start','a-end','b']);assert.equal(c.state.navigating,false);
});

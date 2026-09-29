const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function app(files = ['state.js', 'workflow.js']) {
  const noop = () => {};
  const c = vm.createContext({console, setTimeout, clearTimeout, window:{setTimeout, clearTimeout},
    document:{addEventListener:noop, querySelectorAll:()=>[]}, URL:{revokeObjectURL:noop},
    requestAnimationFrame: cb=>cb()});
  for (const file of files) vm.runInContext(fs.readFileSync(path.join(__dirname,'../../ui',file),'utf8'), c);
  c.state = vm.runInContext('state', c); c.elements = vm.runInContext('elements', c);
  c.showToast=noop;c.renderFileList=noop;c.setSaveState=noop;
  c.state.contextId='folder-A';c.state.activeFileId='a.pdf';c.state.document={document_id:'doc-A',file_id:'a.pdf'};
  return c;
}
function deferred() {let resolve; const promise=new Promise(r=>resolve=r);return {promise,resolve};}
const ok = data=>JSON.stringify({ok:true,data});

test('late status response cannot mark the newly opened PDF', async()=>{
  const c=app();const d=deferred();
  c.webui={isConnected:()=>true,setFileStatusB:()=>d.promise};
  c.state.files=[{file_id:'a.pdf',status:'unreviewed'},{file_id:'b.pdf',status:'unreviewed'}];
  const job=c.setFileStatusF('ok');
  c.state.activeFileId='b.pdf';c.state.document={document_id:'doc-B',status:'unreviewed'};
  d.resolve(ok({file_id:'a.pdf',status:'ok'}));await job;
  assert.equal(c.state.files[1].status,'unreviewed');assert.equal(c.state.document.status,'unreviewed');
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
  const c=app();const d=deferred();const order=[];
  const a=c.enqueueNavigation(async()=>{order.push('a-start');await d.promise;order.push('a-end');});
  const b=c.enqueueNavigation(async()=>{order.push('b');});
  await Promise.resolve();assert.deepEqual(order,['a-start']);d.resolve();await Promise.all([a,b]);
  assert.deepEqual(order,['a-start','a-end','b']);assert.equal(c.state.navigating,false);
});
module.exports={app,deferred};

const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app,deferred}=require('./harness.cjs');

function renderer() {
  const c=app(['state.js','pages.js','scan-zoom.js']);const requests=[],jobs=[];
  c.elements.pagesId={querySelector:()=>({querySelector:()=>({clientWidth:400})})};
  c.elements.zoomId={};c.elements.zoomValueId={};c.devicePixelRatio=1;
  c.crypto={randomUUID:()=>String(requests.length)};
  c.callBackend=async(...args)=>{requests.push(args);const d=deferred();jobs.push(d);await d.promise;};
  return {c,requests,jobs};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('render burst dispatches one page at a time and drops pages no longer visible',async()=>{
  const {c,requests,jobs}=renderer();
  for(let i=0;i<8;i++){c.state.visiblePages.add(i);c.requestPage(i);}
  assert.equal(requests.length,1);
  c.state.visiblePages.clear();c.state.visiblePages.add(7);
  jobs[0].resolve();await tick();assert.equal(requests.length,2);assert.equal(requests[1][3],7);
  jobs[1].resolve();await tick();assert.equal(c.state.rendering,false);
});

test('zoom while a render runs queues only the newest resolution',async()=>{
  const {c,requests,jobs}=renderer();c.state.visiblePages.add(0);c.requestPage(0);
  c.state.ui.zoom_percent=150;c.applyZoom();
  c.state.ui.zoom_percent=200;c.applyZoom();
  await new Promise(resolve=>setTimeout(resolve,200));assert.equal(requests.length,1);
  jobs[0].resolve();await tick();assert.equal(requests.length,2);assert.equal(requests[1][4],800);
  jobs[1].resolve();await tick();
});

test('queued renders from a previous document cannot consume the new document',async()=>{
  const {c,requests,jobs}=renderer();c.state.visiblePages.add(0);c.state.visiblePages.add(1);
  c.requestPage(0);c.requestPage(1);c.state.generation++;c.state.activeFileId='new.pdf';
  c.state.document={file_id:'new.pdf',document_id:'new'};
  jobs[0].resolve();await tick();assert.equal(requests.length,1);assert.equal(c.state.renderQueue.size,0);
});

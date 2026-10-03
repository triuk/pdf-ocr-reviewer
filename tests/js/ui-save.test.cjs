const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app,deferred}=require('./harness.cjs');

test('filter typing and zoom collapse into one save flushed before navigation',async()=>{
  const c=app();const calls=[];
  c.callBackend=async(name,value)=>calls.push([name,JSON.parse(value)]);
  for(const text of ['o','oc','ocr','ocr-','ocr-1']) c.saveUiOptions({name_filter:text});
  c.saveUiOptions({zoom_percent:150});
  await c.enqueueNavigation(async()=>calls.push(['navigate']));
  assert.equal(calls.length,2);assert.equal(calls[0][0],'setUiOptionsB');
  assert.equal(calls[0][1].name_filter,'ocr-1');assert.equal(calls[0][1].zoom_percent,150);
  assert.equal(calls[1][0],'navigate');
});

test('new settings during an in-flight save are drained in order without reverting UI',async()=>{
  const c=app();const first=deferred();const patches=[];
  c.callBackend=async(name,value)=>{patches.push(JSON.parse(value));if(patches.length===1)await first.promise;};
  c.saveUiOptions({zoom_percent:120});const flushing=c.flushUiOptions();
  await Promise.resolve();c.saveUiOptions({zoom_percent:200,overlay:false});first.resolve();
  await flushing;await c.flushUiOptions();
  assert.equal(patches.length,2);assert.equal(patches[1].zoom_percent,200);assert.equal(c.state.ui.zoom_percent,200);
});

test('failed preference save retains latest values but cannot leak into another folder',async()=>{
  const c=app();c.callBackend=async()=>{throw Error('conflict');};
  c.saveUiOptions({name_filter:'old'});assert.equal(await c.flushUiOptions(),false);
  assert.equal(c.state.uiSavePending.patch.name_filter,'old');
  c.state.contextId='folder-B';let called=false;c.callBackend=async()=>{called=true;};
  assert.equal(await c.flushUiOptions(),true);assert.equal(called,false);
});

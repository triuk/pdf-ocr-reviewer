const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app,deferred}=require('./harness.cjs');

function ready() {
  const c=app();
  c.state.files=[{file_id:'a.pdf',review_complete:true,repairs_accepted:false}];
  c.state.document={file_id:'a.pdf',document_id:'doc-A',ocr_sha256:'a'.repeat(64),identity_token:'100:123'};
  c.flushIssueDraft=async()=>true;c.flushFileNote=async()=>true;
  return c;
}

test('acceptance sends the viewed hash and updates only after persistence',async()=>{
  const c=ready(),d=deferred();let payload;
  c.webui={isConnected:()=>true,setRepairAcceptanceB:(file,raw)=>{payload=JSON.parse(raw);return d.promise;}};
  const job=c.setRepairAcceptanceF(true);await new Promise(setImmediate);
  assert.deepEqual(payload,{accepted:true,expected_identity:'100:123',expected_sha256:'a'.repeat(64)});
  assert.equal(c.state.files[0].repairs_accepted,false);
  d.resolve(JSON.stringify({ok:true,data:{file_id:'a.pdf',repairs_accepted:true,repair_accepted_at:'now'}}));
  await job;assert.equal(c.state.files[0].repairs_accepted,true);assert.equal(c.state.document.repairs_accepted,true);
});

test('a late acceptance response cannot mark a newly opened document',async()=>{
  const c=ready(),d=deferred();
  c.webui={isConnected:()=>true,setRepairAcceptanceB:()=>d.promise};
  const job=c.setRepairAcceptanceF(true);await new Promise(setImmediate);
  c.state.activeFileId='b.pdf';c.state.document={file_id:'b.pdf',document_id:'doc-B',repairs_accepted:false};
  d.resolve(JSON.stringify({ok:true,data:{file_id:'a.pdf',repairs_accepted:true}}));await job;
  assert.equal(c.state.document.repairs_accepted,false);assert.equal(c.state.files[0].repairs_accepted,false);
});

test('an unsaved note prevents acceptance without an optimistic green state',async()=>{
  const c=ready();let calls=0;
  c.flushFileNote=async()=>false;c.callBackend=async()=>{calls++;};
  await c.setRepairAcceptanceF(true);
  assert.equal(calls,0);assert.equal(c.state.files[0].repairs_accepted,false);assert.equal(c.state.reviewBusy,false);
});

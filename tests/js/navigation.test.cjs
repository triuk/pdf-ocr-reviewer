const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app}=require('./harness.cjs');

test('navigation combines name and status filters, including a current file leaving the filter',async()=>{
  const c=app(['state.js','workflow.js','files.js']);
  c.elements.nameFilterId={value:'1993'};c.elements.statusFilterId={value:'unreviewed'};
  c.state.files=[{file_id:'a',name:'1993-a',status:'ok'},{file_id:'b',name:'1992-b',status:'unreviewed'},
    {file_id:'c',name:'1993-c',status:'unreviewed'},{file_id:'d',name:'1993-d',status:'ok'}];
  c.state.activeFileId='a';let opened;c.openDocumentF=async id=>{opened=id;};
  await c.moveDocument(1,true);assert.equal(opened,'c');
  c.elements.nameFilterId.value='no match';opened=null;
  await c.moveDocument(1);assert.equal(opened,null);
});

test('zoom supersedes in-flight requests and ignores their packets',async()=>{
  const c=app(['state.js','pages.js']);let width=400;const requests=[];
  c.crypto={randomUUID:()=>String(requests.length)};c.devicePixelRatio=1;
  c.TextDecoder=TextDecoder;c.Blob=Blob;
  c.URL.createObjectURL=()=> 'blob:new';
  c.elements.pagesId={style:{},querySelector:()=>({querySelector:()=>({get clientWidth(){return width;}})})};
  c.state.visiblePages.add(0);c.callBackend=async(...args)=>{requests.push(args);};
  c.renderLoadedPage=()=>{};c.pruneLoadedPages=()=>{};
  await c.requestPage(0);width=800;c.state.ui.zoom_percent=200;c.applyZoom();
  assert.deepEqual(requests.map(a=>a[4]),[400,800]);
  function packet(request){
    const bytes=new TextEncoder().encode(JSON.stringify({request_id:request[1],file_id:'a.pdf',page_index:0,mime:'image/png'}));
    const result=new Uint8Array(4+bytes.length);new DataView(result.buffer).setUint32(0,bytes.length,true);result.set(bytes,4);return result;
  }
  c.pageReadyF(packet(requests[0]));assert.equal(c.state.pageData.size,0);
  c.pageReadyF(packet(requests[1]));assert.equal(c.state.pageData.size,1);
});

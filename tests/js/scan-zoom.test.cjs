const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app}=require('./harness.cjs');

test('image zoom preserves the PDF point under the cursor and limits pan to the page',()=>{
  const c=app(['state.js','scan-zoom.js']);
  const initial={scale:2,x:-0.2,y:-0.6}, anchor={x:0.3,y:0.7};
  const next=c.zoomScanView(initial,3,anchor);
  for(const axis of ['x','y']) {
    assert.ok(Math.abs((anchor[axis]-initial[axis])/initial.scale-(anchor[axis]-next[axis])/next.scale)<1e-9);
  }
  const edge=c.constrainScanView({scale:3,x:4,y:-10});
  assert.equal(edge.x,0);assert.equal(edge.y,-2);
  const small=c.zoomScanView(next,0.5,anchor);
  assert.equal(small.x,0.25);assert.equal(small.y,0.25);
  const reset=c.zoomScanView(next,1,anchor);
  assert.equal(reset.x,0);assert.equal(reset.y,0);
});

test('wheel leaves ordinary scrolling alone, protects marking gestures and respects a slider change',()=>{
  const c=app(['state.js','scan-zoom.js']);
  const handlers={};let clock=1000;
  c.performance={now:()=>clock};
  c.setScanZoom=value=>{c.state.ui.zoom_percent=Math.round(value);};
  const viewport={clientWidth:400,clientHeight:600,clientLeft:1,clientTop:1,
    getBoundingClientRect:()=>({left:10,top:20}),addEventListener:(type,fn)=>{handlers[type]=fn;}};
  c.bindScanViewport(viewport,0);
  const event={ctrlKey:false,deltaY:-120,deltaMode:0,clientX:100,clientY:200,
    preventDefault(){this.prevented=true;},stopPropagation(){}};
  handlers.wheel(event);assert.equal(event.prevented,undefined);assert.equal(c.state.ui.zoom_percent,100);
  event.ctrlKey=true;c.state.markingDrag={};
  handlers.wheel(event);assert.equal(event.prevented,true);assert.equal(c.state.ui.zoom_percent,100);
  c.state.markingDrag=null;handlers.wheel(event);assert.equal(c.state.ui.zoom_percent,120);
  c.state.ui.zoom_percent=200;clock+=10;
  handlers.wheel(event);assert.equal(c.state.ui.zoom_percent,239);
});

test('higher-resolution raster replaces only the image and remains cached when zooming out',async()=>{
  const c=app(['state.js','pages.js','scan-zoom.js']);
  const requests=[];let replaced=0;const displayed={src:'blob:old'};
  c.crypto={randomUUID:()=>String(requests.length)};c.devicePixelRatio=1;c.TextDecoder=TextDecoder;c.Blob=Blob;
  c.URL.createObjectURL=()=> 'blob:new';
  c.elements.pagesId={querySelector:selector=>selector.endsWith(' img') ? displayed : {querySelector:()=>({clientWidth:400})}};
  c.elements.zoomId={};c.elements.zoomValueId={};c.state.visiblePages.add(0);
  c.callBackend=async(...args)=>requests.push(args);c.renderLoadedPage=()=>replaced++;c.pruneLoadedPages=()=>{};
  c.state.pageData.set(0,{targetWidth:400});c.state.ui.zoom_percent=200;c.applyZoom();
  assert.equal(c.state.pageData.size,1);
  await new Promise(resolve=>setTimeout(resolve,200));
  assert.equal(requests[0][4],800);
  const header=new TextEncoder().encode(JSON.stringify({request_id:requests[0][1],file_id:'a.pdf',page_index:0,mime:'image/png'}));
  const packet=new Uint8Array(4+header.length);new DataView(packet.buffer).setUint32(0,header.length,true);packet.set(header,4);
  c.pageReadyF(packet);
  assert.equal(displayed.src,'blob:new');assert.equal(replaced,0);assert.equal(c.state.pageData.get(0).targetWidth,800);
  c.state.ui.zoom_percent=100;await c.requestPage(0);assert.equal(requests.length,1);
});

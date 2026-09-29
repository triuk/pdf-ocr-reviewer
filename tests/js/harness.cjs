const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
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

module.exports={app,deferred};

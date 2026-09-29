const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app}=require('./harness.cjs');

function issue(id,status,page=0) {return {id,status,page_index:page,bbox:[0,0,1,1]};}

test('retained filters include unrepaired and repaired marks but exclude archived marks',()=>{
  const c=app(['state.js','files.js','issues.js']);
  c.state.document.issues=[issue('new','open',1),issue('repaired','fixed'),
    issue('accepted-in-old-version','verified'),issue('deleted','dismissed')];
  assert.deepEqual(Array.from(c.filteredIssues(),i=>i.id),['repaired','new']);
  c.state.issueFilter='archived';
  assert.deepEqual(Array.from(c.filteredIssues(),i=>i.id),['accepted-in-old-version','deleted']);
  c.state.files=[{file_id:'a',name:'1993-a',status:'unreviewed',issue_counts:{fixed:1}},
    {file_id:'b',name:'1993-b',status:'unreviewed',issue_counts:{open:1}},
    {file_id:'c',name:'1993-c',status:'unreviewed',issue_counts:{verified:1,dismissed:1}},
    {file_id:'d',name:'1992-d',status:'unreviewed',issue_counts:{fixed:1}}];
  c.elements.nameFilterId={value:'1993'};c.elements.statusFilterId={value:'all'};
  c.elements.fileIssueFilterId={value:'active'};
  assert.deepEqual(Array.from(c.filteredFiles(),i=>i.file_id),['a','b']);
  c.elements.fileIssueFilterId.value='fixed';
  assert.deepEqual(Array.from(c.filteredFiles(),i=>i.file_id),['a']);
});

test('deleting another repaired box preserves selection; restoring from archive makes it visible',async()=>{
  const c=app(['state.js','issues.js']);
  const retained=issue('keep','fixed');const removed=issue('remove','fixed');
  removed.result={summary:'Prior external repair'};removed.history=[{action:'fixed'}];
  c.state.document.issues=[retained,removed];c.state.selectedIssueId='keep';
  c.elements.issueFilterId={value:'active'};
  c.renderIssueEditor=()=>{};c.refreshIssueViews=()=>{};c.flushIssueDraft=async()=>true;
  const calls=[];
  c.callBackend=async(name,file,id,patch)=>{
    calls.push({name,id,patch:JSON.parse(patch)});
    Object.assign(c.state.document.issues.find(i=>i.id===id),JSON.parse(patch));
    return {file_id:file,issues:c.state.document.issues,issue_counts:{}};
  };
  await c.changeIssueStatus('dismissed','remove');
  assert.equal(c.state.selectedIssueId,'keep');
  assert.equal(retained.status,'fixed');
  assert.equal(removed.status,'dismissed');
  c.state.issueFilter='archived';c.state.selectedIssueId='remove';
  await c.changeIssueStatus('open','remove');
  assert.equal(c.state.issueFilter,'active');
  assert.equal(c.state.selectedIssueId,'remove');
  assert.equal(removed.result.summary,'Prior external repair');
  assert.equal(calls.length,2);
});

test('browsing repaired marks does not change status and old approval shortcuts do nothing',async()=>{
  const c=app(['state.js','issues.js']);
  c.state.document.issues=[issue('later','fixed',2),{...issue('stale','fixed'),stale:true}];
  const selected=[];c.selectIssue=async id=>{selected.push(id);c.state.selectedIssueId=id;};
  await c.navigateIssue(1);await c.navigateIssue(1);
  assert.deepEqual(selected,['stale','later']);
  for (const key of ['v','c','r']) {
    assert.equal(c.handleIssueKeyboard({key,preventDefault(){throw Error('Old shortcut still active');}}),false);
  }
  assert.ok(c.state.document.issues.every(i=>i.status==='fixed'));
});

const {test}=require('node:test');
const assert=require('node:assert/strict');
const {app}=require('./harness.cjs');

test('review visits only matching PDFs with fixed issues and stops when none remain',async()=>{
  const c=app(['state.js','files.js','issues.js']);
  c.state.files=[{file_id:'a',name:'1993-a',status:'unreviewed',issue_counts:{fixed:0}},
    {file_id:'b',name:'1992-b',status:'unreviewed',issue_counts:{fixed:1}},
    {file_id:'c',name:'1993-c',status:'unreviewed',issue_counts:{fixed:1}}];
  c.state.activeFileId='a';c.state.document={issues:[]};
  c.elements.nameFilterId={value:'1993'};c.elements.statusFilterId={value:'all'};
  c.elements.fileIssueFilterId={value:'fixed'};c.elements.issueFilterId={value:'all'};
  const opened=[];const selected=[];
  c.openDocumentF=async id=>{opened.push(id);c.state.activeFileId=id;c.state.document={issues:[{id:'fix-c',status:'fixed',page_index:0,bbox:[0,0,1,1]}]};return true;};
  c.selectIssue=async id=>selected.push(id);
  assert.equal(await c.advanceToNextFixed(),true);
  assert.deepEqual(opened,['c']);assert.deepEqual(selected,['fix-c']);
  c.state.document.issues[0].status='verified';c.state.files[2].issue_counts.fixed=0;
  assert.equal(await c.advanceToNextFixed(),false);
  assert.deepEqual(opened,['c']);
});

test('remaining fixes in the current document take precedence and stale targets remain visible',async()=>{
  const c=app(['state.js','files.js','issues.js']);
  c.elements.nameFilterId={value:''};c.elements.statusFilterId={value:'all'};
  c.elements.fileIssueFilterId={value:'all'};c.elements.issueFilterId={value:'all'};
  c.state.files=[{file_id:'a.pdf',name:'a.pdf',status:'unreviewed',issue_counts:{fixed:2}}];
  c.state.document.issues=[{id:'later',status:'fixed',page_index:2,bbox:[0,0,1,1]},
    {id:'stale',status:'fixed',stale:true,page_index:0,bbox:[0,0,1,1]}];
  let selected;c.selectIssue=async id=>{selected=id;};
  await c.advanceToNextFixed();assert.equal(selected,'stale');
  await c.advanceToNextFixed('later');assert.equal(selected,'later');
});

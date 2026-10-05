/* Move nodes once; tab changes preserve forms and live activity. */
const pageTabs={
 office:[['office','Kantor'],['projects','Proyek'],['activity','Aktivitas'],['insights','Ide & biaya'],['bots','Tim bot'],['jobs','Jadwal']],
 ai:[['ai','AI & model'],['integrations','Akun layanan'],['mcp','MCP']],
 settings:[['settings','Umum'],['skills','Skill'],['memory','Ingatan'],['updates','Update'],['models','Diagnostik']],
};
const selectedPageTabs={},panelScroll=new Map();
for(const [parent,tabs] of Object.entries(pageTabs)) {
 const target=$('#v-'+parent+' .page-in');
 target.querySelectorAll('.section-tabs').forEach(n=>n.remove());
 const original=document.createElement('section');original.id='panel-'+parent;original.className='feature-panel';
 while(target.firstChild)original.append(target.firstChild);
 target.append(original);
 if(parent==='ai') {
  const panel=document.createElement('section');panel.id='panel-integrations';panel.className='feature-panel hidden';
  const title=document.createElement('h2');title.textContent='Akun layanan';panel.append(title);
  for(const selector of ['.integration-list','.social-setup'])panel.append(original.querySelector(selector).closest('.compact-section'));
  target.append(panel);
 }
 if(parent==='office') {
  target.prepend(original.querySelector('.workspace-hero'));
  for(const [id,selector] of [['projects','.project-section'],['activity','#workspaceActivity'],['insights','.office-intelligence']]) {
   const panel=document.createElement('section');panel.id='panel-'+id;panel.className='feature-panel hidden';
   panel.append(original.querySelector(selector));target.append(panel);
   if(id==='activity') {
    panel.prepend(original.querySelector('#officeLog'));
    panel.append(original.querySelector('#officeForm').closest('[data-section]'));
   }
  }
  [...original.querySelectorAll(':scope > [data-section]')].filter(n=>!n.querySelector('form')).forEach(n=>n.remove());
 }
 for(const [child,owner] of Object.entries(pageSections))if(owner===parent) {
  const source=$('#v-'+child+' .page-in');if(!source)continue;source.querySelectorAll('.section-tabs').forEach(n=>n.remove());
  const section=document.createElement('section');section.id='panel-'+child;section.className='feature-panel hidden';
  while(source.firstChild)section.append(source.firstChild);
  target.append(section);$('#v-'+child).remove();
 }
 const nav=document.createElement('nav');nav.className='page-tabs';nav.setAttribute('aria-label','Bagian '+({office:'Workspace',ai:'Koneksi',settings:'Pengaturan'}[parent]));nav.setAttribute('role','tablist');
 tabs.forEach(([id,label])=>{
  const b=document.createElement('button');b.type='button';b.id='tab-'+id;b.textContent=label;b.dataset.panel=id;b.setAttribute('role','tab');b.setAttribute('aria-controls','panel-'+id);
  const panel=$('#panel-'+id);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',b.id);
  b.onclick=()=>go(id);
  b.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const buttons=[...nav.querySelectorAll('button')],index=buttons.indexOf(b),next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[next].click();buttons[next].focus()};
  nav.append(b);
 });
 original.before(nav);selectPageTab(parent,parent,false);
}
// Advanced preferences are reachable without filling the first screen with forms.
for(const group of [...$('#setForm').children]) {
 const heading=group.querySelector(':scope > h4');
 if(!heading||!['Pengaturan AI lanjutan','Otak online','Membuat gambar','Pencarian'].includes(heading.textContent.trim()))continue;
 const details=document.createElement('details');details.className=group.className+' preference-detail';
 const summary=document.createElement('summary');summary.textContent=heading.textContent;heading.remove();details.append(summary);
 while(group.firstChild)details.append(group.firstChild);group.replaceWith(details);
}
function selectPageTab(parent,requested,restore=true) {
 const tabs=pageTabs[parent];if(!tabs)return;
 const page=$('#v-'+parent+' .page'),previous=selectedPageTabs[parent];
 if(previous&&restore)panelScroll.set(previous,page.scrollTop);
 const id=tabs.some(t=>t[0]===requested)?requested:previous||parent;selectedPageTabs[parent]=id;
 tabs.forEach(([key])=>{ $('#panel-'+key).classList.toggle('hidden',key!==id);const b=$('#tab-'+key);b.setAttribute('aria-selected',String(key===id));b.tabIndex=key===id?0:-1; });
 if(restore)page.scrollTop=panelScroll.get(id)||0;
 if(parent==='office'&&id==='office'&&typeof positionOffice==='function')positionOffice();
}
start();

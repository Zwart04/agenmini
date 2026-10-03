/* Keep drafts and reading state in memory. Never store credentials in browser storage. */
const editedFields=new WeakSet(),panelMarkup=new WeakMap(),optionMarkup=new WeakMap();
document.addEventListener('input',e=>{if(e.target.matches('input,textarea,select'))editedFields.add(e.target)});
document.addEventListener('change',e=>{if(e.target.matches('input,textarea,select'))editedFields.add(e.target)});
function syncField(el,value){if(!el||editedFields.has(el)||document.activeElement===el)return;if(el.type==='checkbox')el.checked=!!value;else el.value=value??''}
function clearDraft(root){editedFields.delete(root);root.querySelectorAll('input,textarea,select').forEach(el=>editedFields.delete(el))}
function syncOptions(el,rows,preferred=''){
 const signature=JSON.stringify(rows),focused=document.activeElement===el,current=el.value;
 if(optionMarkup.get(el)!==signature){
  if(focused&&el.options.length)return;
  const options=rows.map(r=>{const option=document.createElement('option');option.value=r.value;option.textContent=r.label;option.disabled=!!r.disabled;return option});
  el.replaceChildren(...options);optionMarkup.set(el,signature);
 }
 const desired=editedFields.has(el)||focused?current:preferred||current;
 if(desired&&![...el.options].some(o=>o.value===desired)){
  const missing=document.createElement('option');missing.value=desired;missing.textContent=desired+' · tidak tersedia';missing.disabled=true;el.append(missing);
 }
 if(desired)el.value=desired;
}
function stablePanel(root,html){
 if(panelMarkup.get(root)===html)return false;
 const open=new Map([...root.querySelectorAll('details[data-ui-key]')].map(el=>[el.dataset.uiKey,el.open]));
 const scroll=new Map([...root.querySelectorAll('[data-ui-scroll]')].map(el=>[el.dataset.uiScroll,[el.scrollTop,el.scrollLeft]]));
 const focus=document.activeElement?.closest('details[data-ui-key]')?.dataset.uiKey;
 const top=root.scrollTop,left=root.scrollLeft;
 root.innerHTML=html;panelMarkup.set(root,html);
 root.querySelectorAll('details[data-ui-key]').forEach(el=>{if(open.has(el.dataset.uiKey))el.open=open.get(el.dataset.uiKey)});
 root.querySelectorAll('[data-ui-scroll]').forEach(el=>{const pos=scroll.get(el.dataset.uiScroll);if(pos){el.scrollTop=pos[0];el.scrollLeft=pos[1]}});
 root.scrollTop=top;root.scrollLeft=left;
 if(focus)[...root.querySelectorAll('details[data-ui-key]')].find(el=>el.dataset.uiKey===focus)?.querySelector('summary')?.focus({preventScroll:true});
 return true;
}

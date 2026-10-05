/* Small accessible controls. Underlying form values remain compatible with the API. */
const designSelects=new WeakMap();let designPopup=null,designDialogQueue=Promise.resolve(),designControlId=0;
function closeDesignOptions(focus=false){if(!designPopup)return;const {panel,anchor}=designPopup;designPopup=null;if(panel.matches(':popover-open'))panel.hidePopover();panel.remove();anchor.setAttribute('aria-expanded','false');if(focus&&anchor.isConnected)anchor.focus()}
function openDesignOptions(anchor,rows,choose,current){
 closeDesignOptions();const panel=document.createElement('div');panel.id='designOptions';panel.className='design-options';panel.setAttribute('role','listbox');panel.setAttribute('aria-label',anchor.getAttribute('aria-label')||'Pilihan');panel.setAttribute('popover','manual');
 const visible=rows.filter(r=>!r.hidden);for(const row of visible){const b=document.createElement('button');b.type='button';b.className='design-option';b.setAttribute('role','option');b.setAttribute('aria-selected',String(row.value===current));b.textContent=row.label;b.disabled=!!row.disabled;b.onclick=()=>{choose(row.value);closeDesignOptions(true)};panel.append(b)}
 if(!visible.length){const p=document.createElement('p');p.className='hint';p.textContent='Belum ada pilihan tersedia.';panel.append(p)}
 document.body.append(panel);designPopup={panel,anchor};anchor.setAttribute('aria-expanded','true');anchor.setAttribute('aria-controls',panel.id);if(panel.showPopover)panel.showPopover();
 const r=anchor.getBoundingClientRect(),vw=document.documentElement.clientWidth,vh=window.visualViewport?.height||innerHeight,width=Math.min(Math.max(r.width,200),vw-24),below=vh-r.bottom-12,above=r.top-12;
 panel.style.width=width+'px';panel.style.left=Math.max(12,Math.min(r.left,vw-width-12))+'px';panel.style.maxHeight=Math.max(80,Math.min(300,Math.max(below,above)))+'px';
 const h=Math.min(panel.scrollHeight,parseFloat(panel.style.maxHeight));panel.style.top=(below>=h||below>=above?r.bottom+6:Math.max(12,r.top-h-6))+'px';
 panel.onkeydown=e=>{const options=[...panel.querySelectorAll('button:not(:disabled)')],index=options.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();options[e.key==='Home'?0:e.key==='End'?options.length-1:(index+(e.key==='ArrowDown'?1:-1)+options.length)%options.length]?.focus()}else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeDesignOptions(true)}};
 return panel;
}
function refreshDesignControls(){
 document.querySelectorAll('select').forEach(select=>{
  let button=designSelects.get(select);if(!button){
   const label=select.getAttribute('aria-label')||[...select.labels].map(l=>{const copy=l.cloneNode(true);copy.querySelectorAll('select,input,textarea,button,datalist').forEach(n=>n.remove());return copy.textContent.trim()}).join(' ')||select.name||'Pilihan';
   button=document.createElement('button');button.type='button';button.id='designSelect'+(++designControlId);button.className=select.className+' design-select';button.setAttribute('role','combobox');button.setAttribute('aria-label',label);button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');button.dataset.selectSource=select.id||select.name;
   select.before(button);select.classList.add('design-select-source');select.tabIndex=-1;select.setAttribute('aria-hidden','true');designSelects.set(select,button);
   const open=focus=>{const panel=openDesignOptions(button,[...select.options].map(o=>({value:o.value,label:o.textContent,disabled:o.disabled,hidden:o.hidden})),v=>{select.value=v;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));refreshDesignControls()},select.value);if(focus)(panel.querySelector('[aria-selected=true]:not(:disabled)')||panel.querySelector('button:not(:disabled)'))?.focus()};
   button.onclick=()=>designPopup?.anchor===button?closeDesignOptions():open(true);
   let search='',searchAt=0;button.onkeydown=e=>{if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();open(true)}else if(e.key.length===1&&e.key!==' '&&!e.ctrlKey&&!e.metaKey){search=Date.now()-searchAt>800?e.key:search+e.key;searchAt=Date.now();const found=[...select.options].find(o=>!o.disabled&&!o.hidden&&o.textContent.toLowerCase().startsWith(search.toLowerCase()));if(found){select.value=found.value;select.dispatchEvent(new Event('change',{bubbles:true}));refreshDesignControls()}}};
  }
  const label=select.selectedOptions[0]?.textContent||'Pilih…';if(button.textContent!==label)button.textContent=label;button.disabled=select.disabled;button.classList.toggle('hidden',select.classList.contains('hidden'));
 });
 document.querySelectorAll('input[list]').forEach(input=>{const id=input.getAttribute('list');input.removeAttribute('list');input.dataset.designSuggestions=id;input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');
  const show=()=>{const list=document.getElementById(id),needle=input.value.toLowerCase();const rows=[...(list?.options||[])].filter(o=>o.value.toLowerCase().includes(needle)).slice(0,30).map(o=>({value:o.value,label:o.label||o.value}));if(!rows.length){closeDesignOptions();return}openDesignOptions(input,rows,v=>{input.value=v;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))},input.value)};
  input.addEventListener('input',show);input.addEventListener('focus',show);input.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();show();designPopup?.panel.querySelector('button')?.focus()}else if(e.key==='Escape'){e.preventDefault();closeDesignOptions()}});
 });
}
function uiDialog(message,initial){
 const run=()=>new Promise(resolve=>{closeDesignOptions();const previous=document.activeElement,dialog=document.createElement('dialog');dialog.className='design-dialog';dialog.setAttribute('aria-labelledby','designDialogTitle');
 const form=document.createElement('form');form.method='dialog';const title=document.createElement('h3');title.id='designDialogTitle';title.textContent=initial===undefined?'Konfirmasi':'Isi informasi';const text=document.createElement('p');text.textContent=message;form.append(title,text);
 let input;if(initial!==undefined){input=document.createElement('input');input.className='inp';input.value=initial;input.setAttribute('aria-label',message);input.autocomplete='off';form.append(input)}
 const actions=document.createElement('div');actions.className='row design-dialog-actions';const cancel=document.createElement('button');cancel.className='btn';cancel.textContent='Batal';cancel.value='cancel';cancel.formNoValidate=true;const accept=document.createElement('button');accept.className='btn pri';accept.textContent=initial===undefined?'Lanjutkan':'Simpan';accept.value='accept';actions.append(cancel,accept);form.append(actions);dialog.append(form);document.body.append(dialog);
 dialog.addEventListener('close',()=>{const result=dialog.returnValue==='accept'?(input?input.value:true):(input?null:false);dialog.remove();if(previous?.isConnected)previous.focus();resolve(result)},{once:true});dialog.showModal();(input||cancel).focus();
 });const result=designDialogQueue.then(run);designDialogQueue=result.catch(()=>{});return result;
}
function uiConfirm(message){return uiDialog(message)}
function uiPrompt(message,initial=''){return uiDialog(message,initial)}
document.addEventListener('click',e=>{if(designPopup&&!designPopup.panel.contains(e.target)&&!designPopup.anchor.contains(e.target))closeDesignOptions();if(e.target.tagName==='LABEL'){const source=e.target.control;if(source&&designSelects.has(source)){e.preventDefault();designSelects.get(source).focus()}}setTimeout(refreshDesignControls,0)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&designPopup){e.preventDefault();e.stopPropagation();closeDesignOptions(true)}},true);
document.addEventListener('change',()=>queueMicrotask(refreshDesignControls));
document.addEventListener('invalid',e=>{e.preventDefault();e.target.setAttribute('aria-invalid','true');toast(e.target.validationMessage||'Lengkapi isian yang ditandai.');(designSelects.get(e.target)||e.target).focus()},true);
document.addEventListener('input',e=>e.target.removeAttribute('aria-invalid'));
window.addEventListener('resize',()=>closeDesignOptions());document.addEventListener('scroll',e=>{if(designPopup&&!designPopup.panel.contains(e.target))closeDesignOptions()},true);
new MutationObserver(changes=>{if(changes.some(c=>c.target.matches?.('select,datalist,option')||(c.type==='attributes'&&c.target.matches?.('select'))||[...c.addedNodes].some(n=>n.nodeType===1&&(n.matches('select,input[list]')||n.querySelector('select,input[list]')))))refreshDesignControls()}).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','hidden','class']});
refreshDesignControls();

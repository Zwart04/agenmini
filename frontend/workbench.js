/* Native browser rendering and a small textarea editor; no Monaco/WebView server. */
window.Workbench=(()=>{
 document.querySelector('.chat-model-bar').append(document.querySelector('#workbenchOpen'));
 const accessButton=document.createElement('button');accessButton.id='chatAccess';accessButton.type='button';accessButton.className='btn sm';accessButton.textContent='Dengan izin';document.querySelector('.chat-model-bar').append(accessButton);
 let opened=false,file=null,dirty=false,timer=null,cursor=0,chat=null,loading=false,tab='code';const seen=new Set();
 const panel=document.querySelector('#workbench'),editor=document.querySelector('#wbEditor');
 function syncEditor(){
  const path=file?.path||'',lines=editor.value.split('\n');
  document.querySelector('#wbLines').textContent=lines.map((_,i)=>i+1).join('\n');
  document.querySelector('#wbFileName').textContent=path.split('/').at(-1)||'Ruang kerja';
  document.querySelector('#wbFileName').title=path;
  document.querySelector('#wbFileState').textContent=dirty?'Belum disimpan':file?.sha256?'Tersimpan':'Draf';
  document.querySelector('#wbFileState').classList.toggle('is-dirty',dirty);
  const ext=path.split('.').at(-1);document.querySelector('#wbLanguage').textContent=({js:'JavaScript',ts:'TypeScript',py:'Python',html:'HTML',css:'CSS',json:'JSON',md:'Markdown'})[ext]||'Teks';
  position();
 }
 function position(){const prefix=editor.value.slice(0,editor.selectionStart).split('\n');document.querySelector('#wbPosition').textContent='Baris '+prefix.length+' · Kolom '+(prefix.at(-1).length+1)}
 editor.addEventListener('scroll',()=>{document.querySelector('#wbLines').scrollTop=editor.scrollTop});
 editor.addEventListener('click',position);editor.addEventListener('keyup',position);
 editor.addEventListener('keydown',e=>{if(e.key==='Tab'){e.preventDefault();editor.setRangeText('  ',editor.selectionStart,editor.selectionEnd,'end');dirty=true;syncEditor()}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();document.querySelector('#wbSave').click()}});
 const overlayMedia=matchMedia('(max-width:1200px)');
 function syncOverlay(){const overlay=opened&&overlayMedia.matches;document.querySelector('#app>main').inert=overlay;document.querySelector('#side').inert=overlay;panel.setAttribute('role',overlay?'dialog':'complementary');if(overlay)panel.setAttribute('aria-modal','true');else panel.removeAttribute('aria-modal')}
 overlayMedia.addEventListener('change',syncOverlay);
 const say=t=>{document.querySelector('#wbInfo').textContent=t;syncEditor()};
 function selectTab(name){tab=name;panel.querySelectorAll('[data-wb-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.wbTab===name)));panel.querySelectorAll('[data-wb-view]').forEach(v=>v.hidden=v.dataset.wbView!==name)}
 async function refresh(){if(loading)return;loading=true;try{const d=await api('/api/workbench/files'),s=document.querySelector('#wbFiles'),old=s.value;s.replaceChildren(new Option('Pilih berkas…',''));d.files.forEach(p=>s.add(new Option(p,p)));s.value=file?.path||old;window.refreshDesignControls?.();say(d.truncated?'Daftar dibatasi 300 berkas.':'Berkas ruang kerja · perubahan disimpan dengan pemeriksaan konflik.')}catch(e){say(e.message)}finally{loading=false}}
 async function choose(path){if(!path)return;if(dirty&&!(await uiConfirm('Ada perubahan belum disimpan. Buka berkas lain?')))return;try{file=await api('/api/workbench/file?path='+encodeURIComponent(path));editor.value=file.content;dirty=false;document.querySelector('#wbFiles').value=path;say(path);selectTab('code')}catch(e){say(e.message)}}
 function event(data){
  const identity=JSON.stringify([data.run_id,data.kind,data.call_id,data.step,data.path,data.sha256,data.outcome]);if(seen.has(identity))return;seen.add(identity);if(seen.size>2000)seen.delete(seen.values().next().value);
  const list=document.querySelector('#wbLog'),line=document.createElement('li');line.textContent=(data.kind||'aktivitas')+(data.tool?' · '+data.tool:'')+(data.path?' · '+data.path:'')+(data.outcome?' · '+data.outcome:'');list.append(line);while(list.children.length>100)list.firstChild.remove();list.scrollTop=list.scrollHeight;
  if(data.kind==='file/change'){
   if(dirty){say('Agen mengubah '+data.path+'. Perubahan Anda tetap di editor; simpan atau salin sebelum membuka versi agen.');return}
   if(data.truncated){say('Perubahan besar tersedia di server; pilih berkas untuk membaca versi lengkap.');return}
   file={path:data.path,content:data.after,sha256:data.sha256};editor.value=data.after;dirty=false;
   document.querySelector('#wbDiff').textContent='SEBELUM\n'+(data.before||'(berkas baru)')+'\n\nSESUDAH\n'+data.after;
   say('Agen memperbarui '+data.path);if(opened)refresh();
  }
 }
 async function poll(){clearTimeout(timer);if(!opened)return;if(!document.hidden&&chat){try{const d=await api('/api/workbench/events/'+chat+'?after='+cursor);for(const row of d.events){cursor=row.id;event({run_id:row.run_id,kind:row.kind,...row.data})}}catch(e){say(e.message)}}timer=setTimeout(poll,S.busy?2500:10000)}
 function bindChat(id){if(chat!==id){chat=id;cursor=0;seen.clear();document.querySelector('#wbLog').replaceChildren()}if(opened)poll()}
 function open(){opened=true;panel.hidden=false;document.querySelector('#app').classList.add('workbench-open');document.querySelector('#workbenchOpen').setAttribute('aria-expanded','true');syncOverlay();document.querySelector('#wbClose').focus();refresh();poll()}
 function close(){if(dirty){uiConfirm('Tutup panel dengan perubahan belum disimpan?').then(ok=>{if(ok){dirty=false;close()}});return}opened=false;panel.hidden=true;clearTimeout(timer);syncOverlay();document.querySelector('#app').classList.remove('workbench-open');document.querySelector('#workbenchOpen').setAttribute('aria-expanded','false');document.querySelector('#workbenchOpen').focus()}
 async function preview(){
  if(!file?.sha256||!file.path.endsWith('.html'))return say('Pilih berkas HTML tersimpan untuk preview; draf belum dapat dijalankan.');
  if(dirty)return say('Simpan dahulu agar preview sesuai berkas server.');
  const source=file,doc=new DOMParser().parseFromString(source.content,'text/html'),base=source.path.split('/').slice(0,-1);
  async function local(url){if(/^(?:[a-z]+:|\/\/|\/)/i.test(url))throw new Error('Preview offline tidak memuat URL eksternal.');const parts=[...base];for(const p of url.split(/[?#]/)[0].split('/')){if(p==='..'){if(!parts.length)throw new Error('Jalur preview tidak valid');parts.pop()}else if(p&&p!=='.')parts.push(p)}return (await api('/api/workbench/file?path='+encodeURIComponent(parts.join('/')))).content}
  try{
   for(const link of [...doc.querySelectorAll('link[rel=stylesheet]')]){const style=doc.createElement('style');style.textContent=await local(link.getAttribute('href'));link.replaceWith(style)}
   for(const script of [...doc.querySelectorAll('script[src]')]){const code=await local(script.getAttribute('src'));script.removeAttribute('src');script.textContent=code}
   doc.querySelectorAll('base,meta[http-equiv],iframe,object,embed').forEach(n=>n.remove());
   const policy=doc.createElement('meta');policy.httpEquiv='Content-Security-Policy';policy.content="default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; img-src data: blob:; media-src blob:; connect-src 'none'; form-action 'none'; base-uri 'none'";doc.head.prepend(policy);
   document.querySelector('#wbFrame').srcdoc='<!doctype html>'+doc.documentElement.outerHTML;selectTab('preview');say('Preview offline isolasi · API, import module dan aset eksternal memerlukan server proyek.');
  }catch(e){say(e.message)}
 }
 document.querySelector('#workbenchOpen').onclick=open;document.querySelector('#wbClose').onclick=close;
 panel.querySelectorAll('[data-wb-tab]').forEach(b=>b.onclick=()=>selectTab(b.dataset.wbTab));
 document.querySelector('#wbFiles').onchange=e=>choose(e.target.value);document.querySelector('#wbRefresh').onclick=refresh;
 editor.oninput=()=>{dirty=true;say('Perubahan belum disimpan')};
 document.querySelector('#wbSave').onclick=async()=>{if(!file?.sha256)return say('Draf agen belum divalidasi/disimpan; tunggu hasil atau buka berkas tersimpan.');try{file=await api('/api/workbench/file',{method:'POST',body:{path:file.path,content:editor.value,sha256:file.sha256}});dirty=false;say('Tersimpan · '+file.path)}catch(e){say(e.message)}};
 document.querySelector('#wbPreview').onclick=preview;
 document.querySelector('#wbBrowse').onsubmit=e=>{e.preventDefault();try{const url=new URL(document.querySelector('#wbAddress').value);if(!['https:','http:'].includes(url.protocol)||url.username||url.password)throw new Error('Gunakan URL HTTP/HTTPS tanpa kredensial.');document.querySelector('#wbWeb').src=url.href;document.querySelector('#wbExternal').href=url.href;say('Situs dapat menolak embedding. Gunakan Buka tab jika kosong; ini panel tampilan, bukan browser otomatis agen.')}catch(err){say(err.message)}};
 panel.addEventListener('keydown',e=>{if(e.key==='Escape'&&!e.target.matches('textarea'))close();if(e.key==='Tab'&&overlayMedia.matches){const nodes=[...panel.querySelectorAll('button:not(:disabled),input,textarea,a[href],iframe,[tabindex="0"]')].filter(n=>n.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}});
 document.querySelector('#chatAccess').onclick=async()=>{if(S.busy)return toast('Tunggu tugas selesai sebelum mengganti izin.');try{const s=await api('/api/settings'),enable=s.full_access!=='1';if(enable&&!(await uiConfirm('Akses penuh melewati persetujuan alat Agen Mini untuk tugas Anda. Batas folder tetap berlaku. Runtime eksternal memiliki izin sendiri. Aktifkan?')))return;await api('/api/settings',{method:'POST',body:{full_access:enable?'1':'0'}});await access()}catch(e){toast(e.message)}};
 async function access(){const s=await api('/api/settings'),b=document.querySelector('#chatAccess');b.textContent=s.full_access==='1'?'Akses penuh':'Dengan izin';b.setAttribute('aria-pressed',String(s.full_access==='1'))}
 return {event,bindChat,open,choose,access,draft(data){if(dirty)return;file={path:data.path,content:data.content,sha256:null};editor.value=data.content;say('Draf agen · '+data.path+' · belum disimpan/divalidasi')},busy(value){document.querySelector('#app').classList.toggle('agent-working',value)}};
})();

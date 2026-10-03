/* Browser-only motion and one active clock. The existing SSE carries actual bot states. */
function setMotion(value){document.documentElement.dataset.motion=value==='off'?'off':'on';$('#motionSetting').value=document.documentElement.dataset.motion;try{localStorage.setItem('motion',value)}catch(e){}}
try{setMotion(localStorage.getItem('motion')||'on')}catch(e){setMotion('on')}
$('#motionSetting').onchange=e=>setMotion(e.target.value);
document.addEventListener('visibilitychange',()=>{document.documentElement.dataset.paused=String(document.hidden);if(document.hidden){clearInterval(runtimeClock);runtimeClock=null}document.querySelectorAll('.dot-asset').forEach(img=>{if(document.hidden){img.dataset.resumeSrc=img.getAttribute('src');img.src=img.src.replace(/-(idle|thinking|writing|listening|success|error|alert)\.svg$/,'-asleep.svg')}else if(img.dataset.resumeSrc){img.src=img.dataset.resumeSrc;delete img.dataset.resumeSrc}})});
let runtimeClock=null,runtimeStarted=0,runtimeKey='',importRows=[];
function renderRuntime(r){
 const labels={queued:'Menunggu',preparing:'Menyiapkan',downloading:'Mengunduh',verifying:'Memeriksa SHA256',loading:'Menghubungkan AI',ready:'Siap',failed:'Gagal',stopped:'Belum aktif'};
 const busy=['queued','preparing','downloading','verifying','loading'].includes(r.phase);
 $('#runtimePhase').textContent=labels[r.phase]||'Memeriksa';$('#runtimeStatus').textContent=r.message||'';
 $('#runtimeSpinner').classList.toggle('hidden',!busy);$('#localRuntime').classList.toggle('busy',busy);
 $('#runtimeProgress').classList.toggle('hidden',r.phase!=='downloading');
 let elapsed=$('#runtimeElapsed');if(!elapsed){elapsed=document.createElement('small');elapsed.id='runtimeElapsed';$('#runtimeStatus').after(elapsed)}
 const key=r.model_id+':'+(r.started_at||'');
 if(key!==runtimeKey){runtimeKey=key;runtimeStarted=r.started_at?1000*r.started_at:Date.now()}
 clearInterval(runtimeClock);runtimeClock=null;elapsed.classList.toggle('hidden',!busy);
 if(busy){const tick=()=>{if(!document.hidden)elapsed.textContent='Berjalan '+Math.max(0,Math.floor((Date.now()-runtimeStarted)/1000))+' dtk · status diperiksa otomatis'};tick();runtimeClock=setInterval(tick,1000)}
 if(r.phase!=='downloading')$('#runtimeBytes').textContent='';
 $$('[data-mode]').forEach(b=>b.disabled=['queued','preparing','downloading','verifying'].includes(r.phase));
}
function showActivity(ev){
 if(typeof updateOfficePresence==='function')updateOfficePresence(ev);
 if(S.busy&&ev.bot===S.bot?.id&&ev.action){const label=$('#thread .activity-label');if(label)label.textContent=ev.action}
}
async function loadChatModels(backend,keep=false){
 const bot=S.bot?.id;if(!bot)return;
 $('#chatModelInfo').innerHTML='<span class="runtime-spinner"></span> Memeriksa pilihan…';
 try{
  let d=await api('/api/chat-models/'+encodeURIComponent(bot)+(backend===undefined?'':'?backend='+encodeURIComponent(backend)));
  if(S.bot?.id!==bot)return;
  if(!keep)$('#chatBackend').value=d.backend;
  $('#chatModel').innerHTML=d.models.length?d.models.map(m=>`<option value="${esc(m.id)}" ${m.id===d.model?'selected':''} ${m.fits===false?'disabled':''}>${esc(m.name||m.id)}${m.fits===false?' · RAM kurang':''}</option>`).join(''):'<option value="">'+(backend||d.backend?'Belum ada model tersedia':'Model mengikuti bot')+'</option>';
  $('#chatModelInfo').textContent=d.backend?'Pilihan tersimpan untuk percakapan ini.':'Bawaan bot: '+d.default_backend+' · '+d.default_model;
 }catch(e){$('#chatModelInfo').textContent=e.message;$('#chatModel').innerHTML='<option value="">Hubungkan provider di Koneksi</option>'}
}
$('#chatBackend').onchange=e=>loadChatModels(e.target.value,true);
$('#chatModelApply').onclick=async()=>{try{const d=await api('/api/chat-models/'+encodeURIComponent(S.bot.id),{method:'POST',body:{backend:$('#chatBackend').value,model:$('#chatModel').value}});toast(d.message);await loadChatModels()}catch(e){sayError(e)}};
$('#modelImportForm').onsubmit=async e=>{e.preventDefault();$('#importInfo').innerHTML='<span class="runtime-spinner"></span> Memeriksa metadata dan hash sumber…';try{
 const d=await api('/api/local-models/inspect',{method:'POST',body:{source:$('#importSource').value,name:$('#importName').value}});importRows=d.models;
 $('#importFile').innerHTML=importRows.map(m=>`<option value="${esc(m.id)}">${esc(m.original_file)} · ${m.download_gb} GB · RAM ≥ ${m.min_ram_gb} GB</option>`).join('');$('#importFileRow').classList.remove('hidden');$('#importSave').classList.remove('hidden');$('#importInfo').textContent='Pilih berkas, tambahkan, lalu klik Pilih & unduh di kartu model. Belum ada bobot yang diunduh.';
 }catch(e){$('#importInfo').textContent=e.message;$('#importSave').classList.add('hidden')}};
$('#importSave').onclick=async()=>{try{await api('/api/local-models/import',{method:'POST',body:{source:$('#importSource').value,name:$('#importName').value,id:$('#importFile').value}});toast('Model ditambahkan. Pilih & unduh untuk memakainya.');await loadLocalModels()}catch(e){sayError(e)}};
// Show a ring for asynchronous buttons/forms, restoring the original state on every exit path.
function busyHandler(el,fn,event){const old=el.disabled;let result;try{result=fn(event)}catch(e){throw e}if(!result?.then)return result;el.classList.add('is-loading');el.disabled=true;el.setAttribute('aria-busy','true');return Promise.resolve(result).finally(()=>{el.classList.remove('is-loading');el.removeAttribute('aria-busy');if(!S.busy)el.disabled=old})}
function wireBusy(root=document){
 root.querySelectorAll('button').forEach(b=>{if(!b.onclick||b.onclick.activityWrapped)return;const fn=b.onclick;b.onclick=function(e){return busyHandler(b,ev=>fn.call(b,ev),e)};b.onclick.activityWrapped=true});
 root.querySelectorAll('form').forEach(f=>{if(!f.onsubmit||f.onsubmit.activityWrapped)return;const fn=f.onsubmit;f.onsubmit=function(e){const b=e.submitter||f.querySelector('button[type=submit],button:not([type])');return b?busyHandler(b,ev=>fn.call(f,ev),e):fn.call(f,e)};f.onsubmit.activityWrapped=true});
}
$('#checkTools').onclick=async()=>{const box=$('#toolChecks');box.innerHTML='<span class="runtime-spinner"></span> Menjalankan uji di server…';try{const d=await api('/api/tools/check',{method:'POST',body:{}});box.innerHTML=d.checks.map(r=>`<p><strong>${r.ok?'✓':'!'} ${esc(r.name)}</strong><br>${esc(r.message)}</p>`).join('')+`<p>${esc(d.note)}</p>`}catch(e){box.textContent=e.message}};
wireBusy();

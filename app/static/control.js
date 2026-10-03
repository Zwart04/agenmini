/* Native admin panels. No framework, external font, image bundle or animation loop. */
const dotShapes=['round','triangle','square','cloud','star','flame'];
const dotState=(b,t)=>b.status==='working'?({tool:'writing',delegating:'listening',queued:'listening'}[b.phase]||b.phase||'thinking'):({done:'success',failed:'error',waiting:'alert',queued:'listening'})[b.last_status||t?.status]||'idle';
const officeColors=['#f5ba92','#b1c9e9','#beb2db','#b6d4b4','#e7c578','#dfa6bb'];
let aiDraftMode=null, aiGeneration=0, logGeneration=0;
let openedOfficeLog=null,officeRoomFingerprint="",officeTasksFingerprint="",officeLogFingerprint="",officeTimer, aiTimer, oauthFlow=null, oauthTimer, mcpDiscovered=[], editedSkill=null;
const sayError=e=>toast(e.message || String(e));
function officeTaskSummary(text){
 const stage=String(text||'').match(/(?:^|\n)Tahap:\s*([^\n]+)/);
 const line=(stage?stage[1]:String(text||'').replace(/\s+/g,' ').trim());
 return line.length>140?line.slice(0,137)+'…':line;
}
$('#clearOfficeHistory').onclick=async()=>{try{const d=await api('/api/office/history',{method:'DELETE'});officeTasksFingerprint='';officeLogFingerprint='';toast(d.cleared+' aktivitas selesai/gagal dibersihkan');await loadOffice()}catch(e){sayError(e)}};

let taskHistoryPage=0,taskHistoryRows=[];
function showDetail(title,html){
 let dialog=$('#recordDetail');
 if(!dialog){dialog=document.createElement('dialog');dialog.id='recordDetail';dialog.className='record-detail';document.body.append(dialog);dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});}
 dialog.innerHTML='<header><h3>'+esc(title)+'</h3><button type="button" class="btn sm" aria-label="Tutup rincian">Tutup</button></header><div class="record-detail-body">'+html+'</div>';
 dialog.querySelector('button').onclick=()=>dialog.close();if(!dialog.open)dialog.showModal();dialog.querySelector('.record-detail-body').scrollTop=0;
}
function renderTaskHistory(rows){
 rows=[...rows].sort((a,b)=>Number(!!b.approval)-Number(!!a.approval));taskHistoryRows=rows;const fingerprint=JSON.stringify([rows,taskHistoryPage]);if(fingerprint===officeTasksFingerprint)return;
 officeTasksFingerprint=fingerprint;const count=Math.ceil(rows.length/8);taskHistoryPage=Math.max(0,Math.min(taskHistoryPage,count-1));
 const labels={queued:'Antre',working:'Bekerja',done:'Selesai',failed:'Perlu perbaikan',waiting:'Perlu tindakan',paused:'Dijeda'};
 $('#officeTasks').innerHTML=rows.slice(taskHistoryPage*8,taskHistoryPage*8+8).map(t=>`<article class="activity-row"><div class="grow"><div class="row"><b>${esc(t.source==='owner'?'Anda':S.bots.find(b=>b.id===t.source)?.name||t.source)} → ${esc(S.bots.find(b=>b.id===t.target)?.name||t.target)}</b><span class="pill">${labels[t.status]||esc(t.status)}</span></div><p class="office-task-summary">${esc(officeTaskSummary(t.text))}</p><div class="row"><button class="btn sm" data-task-read="${t.id}">${t.approval?'Tinjau tindakan':'Baca lengkap'}</button>${t.status==='queued'?`<button class="btn sm" data-task-edit="${t.id}">Ubah</button>`:''}${t.status!=='working'?`<button class="btn sm ghost danger" data-task-delete="${t.id}">Hapus</button>`:''}</div></div></article>`).join('')||empty('Belum ada aktivitas.');
 if(rows.length>8)$('#officeTasks').insertAdjacentHTML('beforeend',`<nav class="record-pagination" aria-label="Halaman aktivitas"><button class="btn sm" data-task-page="-1" ${taskHistoryPage===0?'disabled':''}>Sebelumnya</button><span>${taskHistoryPage+1} / ${count} · ${rows.length} aktivitas</span><button class="btn sm" data-task-page="1" ${taskHistoryPage>=count-1?'disabled':''}>Berikutnya</button></nav>`);
 $$('[data-task-page]').forEach(b=>b.onclick=()=>{taskHistoryPage+=Number(b.dataset.taskPage);renderTaskHistory(taskHistoryRows)});
 $$('[data-task-read]').forEach(b=>b.onclick=()=>{const t=rows.find(t=>t.id===Number(b.dataset.taskRead));showDetail('Aktivitas tim','<h4>Tugas</h4><pre class="detail-text">'+esc(t.text)+'</pre>'+(t.result?'<h4>Hasil</h4><pre class="detail-text">'+esc(t.result)+'</pre>':'')+(t.approval?`<section class="approval-preview"><h4>Tinjau izin</h4><p>${esc(t.approval.reason)}</p><pre class="detail-text">${esc(t.approval.args)}</pre><div class="row"><button class="btn pri" data-office-approve="${t.id}">Izinkan</button><button class="btn" data-office-deny="${t.id}">Tolak</button></div></section>`:''));
 $$('[data-office-approve],[data-office-deny]').forEach(a=>a.onclick=async()=>{a.disabled=true;try{await api('/api/office/approval/'+t.id,{method:'POST',body:{ok:!!a.dataset.officeApprove}});$('#recordDetail').close();officeTasksFingerprint='';await loadOffice()}catch(e){sayError(e);a.disabled=false}});
 });
 $$('[data-task-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('Hapus aktivitas ini?'))return;try{await api('/api/office/tasks/'+b.dataset.taskDelete,{method:'DELETE'});officeTasksFingerprint='';await loadOffice()}catch(e){sayError(e)}});
 $$('[data-task-edit]').forEach(b=>b.onclick=async()=>{const t=rows.find(t=>t.id===Number(b.dataset.taskEdit)),text=prompt('Ubah tugas yang belum dijalankan:',t.text);if(text===null)return;try{await api('/api/office/tasks/'+t.id,{method:'PATCH',body:{text}});officeTasksFingerprint='';await loadOffice()}catch(e){sayError(e)}});
}

async function loadOffice(){
  clearTimeout(officeTimer);
  try{
    const d=await api('/api/office');
    renderOfficeScene(d);
    await loadOfficeLearning();
    $('#officeStats').innerHTML=`<b>${d.bots.filter(b=>b.status==='working').length} bot bekerja</b><span>${d.tasks.filter(t=>t.status==='queued').length} tugas menunggu · ${d.bots.length} anggota tim</span><small>Aktivitas langsung dari server</small>`;
    if(typeof loadProjects==='function')await loadProjects();
    $('#officeActivityCount').textContent='· '+d.tasks.length;

    syncOptions($('#officeLogBot'),d.bots.map(b=>({value:b.id,label:b.name})));
    const target=$('#officeTarget').value||'orchestrator';
    $('#officeTarget').innerHTML=d.bots.map(b=>`<option value="${esc(b.id)}">${esc(b.name)}</option>`).join('');
    if(target)$('#officeTarget').value=target;
 const labels={queued:'Menunggu',working:'Dikerjakan',done:'Selesai',failed:'Gagal',waiting:'Butuh tindakan'};
    renderTaskHistory(d.tasks);
    if(openedOfficeLog)await showOfficeLog(openedOfficeLog,true);
    if(typeof wireBusy==='function')wireBusy($('#v-office'));
    if(S.view==='office'&&!document.hidden) officeTimer=setTimeout(loadOffice,d.bots.some(b=>b.status==='working')?5000:15000);
  }catch(e){sayError(e)}
}
$('#officeForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/office',{method:'POST',body:{target:$('#officeTarget').value,text:$('#officeText').value}});$('#officeText').value='';loadOffice()}catch(e){sayError(e)}};

async function loadAI(){
  clearTimeout(aiTimer);
  const generation=++aiGeneration;
  await loadIntegrations();
  await loadSocial();
  await loadLocalModels();
  const settings=await api('/api/settings');
  if(generation!==aiGeneration)return;
  const active=settings.llm_backend,mode=aiDraftMode||active;
  $('#autoPanel').classList.toggle('hidden',mode!=='auto');
  $$('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode))});
  $('#enableEngine').textContent=mode===active?'Siapkan / perbaiki sumber':'Siapkan '+({auto:'Smart Router',local:'model lokal',router:'9router',freellmapi:'FreeLLMAPI',online:'API langsung'}[mode]||mode);
  $('#engineGuide').textContent=({auto:'Hubungkan kandidat dahulu, lalu aktifkan Smart Router. Keputusan dan model aktual dicatat pada jawaban.',local:'Klik Siapkan, pilih model yang cocok dengan RAM, tunggu status Siap, lalu Uji koneksi.',router:'Klik Siapkan 9router, tambahkan provider/API key atau login akun, pilih model, lalu Uji koneksi.',freellmapi:'Klik Siapkan FreeLLMAPI, pilih provider dan masukkan API key, pilih model tersedia, lalu Uji koneksi.',online:'Isi URL /v1, API key dan ID model; simpan, lalu Uji koneksi.'})[mode];
  $('#aiMode').textContent=({auto:'Smart Router Agen Mini',router:'9router',local:'Model lokal tanpa Ollama',compatible:'API kompatibel',ollama:'Ollama',freellmapi:'FreeLLMAPI',online:'API langsung'})[active]||active;
  $('#routerPanel').classList.toggle('hidden',!['router','compatible'].includes(mode));
  $('#freePanel').classList.toggle('hidden',mode!=='freellmapi');
  $('#routerHeading').classList.toggle('hidden',!['router','compatible'].includes(mode));
  $('#routerStatus').classList.toggle('hidden',!['router','compatible'].includes(mode));
  $('#localModelSection').classList.toggle('hidden',mode!=='local');
  $('#localRuntime').classList.toggle('hidden',mode!=='local');
  if(mode!=='local')renderRuntime(await api('/api/runtime'));

  $('#localRuntime [data-section]').classList.toggle('hidden',mode!=='local');
  $('#directApiForm').classList.toggle('hidden',mode!=='online');
  if(mode==='online'){['Url','Key','Model'].forEach((field,i)=>syncField($('#directApi'+field),settings[['online_base','online_key','online_model'][i]]||''));}
  if(mode==='auto'){await loadAutoRoutes();if(S.view==='ai'&&!document.hidden)aiTimer=setTimeout(()=>loadAI().catch(sayError),10000);return;}
  if(mode==='freellmapi'){await loadFree(generation);if(generation!==aiGeneration)return;if(S.view==='ai'&&!document.hidden)aiTimer=setTimeout(()=>loadAI().catch(sayError),10000);return;}
  if(mode==='online'){$('#routerStatus').textContent='API langsung: atur URL dan kunci di bawah.';return;}
  if(mode==='local'){$('#routerStatus').textContent='Mode lokal aktif. Pilih 9router untuk menyambungkan provider.';if(S.view==='ai'&&!document.hidden)aiTimer=setTimeout(()=>loadAI().catch(sayError),5000);return;}
  if(!$('#routerModel').options.length)$('#routerStatus').textContent='Membaca provider dan model…';
  try{
    const d=await api('/api/router');if(generation!==aiGeneration)return;
    $('#routerStatus').textContent='Provider terhubung · '+d.models.length+' model chat. '+(d.model_note||'');
    $('#routerConnections').innerHTML=d.connections.map(c=>`<div class="r"><div class="grow"><b>${esc(c.name||c.provider)}</b><div class="sub">${esc(c.email||c.provider)} · ${esc(c.testStatus||'terhubung')}</div>${c.lastError?`<section data-section><h4>Lihat kendala provider</h4><p class="hint">${esc(c.lastError)}</p></section>`:''}</div><button class="btn sm" data-remove-provider="${esc(c.id)}">Hapus</button></div>`).join('')||empty('Belum ada provider. Tambahkan API key atau login OAuth di bawah.');
    $$('[data-remove-provider]').forEach(x=>x.onclick=async()=>{if(confirm('Hapus koneksi provider ini?')){try{await api('/api/router/provider/'+encodeURIComponent(x.dataset.removeProvider),{method:'DELETE'});loadAI()}catch(e){sayError(e)}}});
 syncOptions($('#routerModel'),d.models.map(m=>({value:m.id,label:(m.name||m.id)+' · '+m.id})),d.active_model);
 syncOptions($('#oauthProvider'),d.device_providers.concat(d.code_providers).map(p=>({value:p,label:p})),'');
 syncOptions($('#apiProvider'),d.api_providers.map(p=>({value:p,label:p})),'');
  }catch(e){$('#routerStatus').textContent=e.message}
  if(S.view==='ai'&&!document.hidden)aiTimer=setTimeout(()=>loadAI().catch(sayError),5000);
}
$$('[data-mode]').forEach(b=>b.onclick=()=>{aiDraftMode=b.dataset.mode;loadAI().catch(sayError)});
$('#enableEngine').onclick=async()=>{try{const mode=aiDraftMode||(await api('/api/settings')).llm_backend;const d=await api('/api/mode',{method:'POST',body:{mode}});toast(d.message);loadAI()}catch(e){sayError(e)}};
$('#testEngine').onclick=async()=>{const box=$('#engineTest');box.innerHTML='<span class="runtime-spinner"></span> Menunggu jawaban nyata dari model…';try{const mode=aiDraftMode||(await api('/api/settings')).llm_backend;const model=mode==='router'?$('#routerModel').value:mode==='freellmapi'?$('#freeModel').value:'';const d=await api('/api/ai/test',{method:'POST',body:{backend:mode,model}});box.textContent=(d.ok?'✓ Model menjawab benar':'Model menjawab, tetapi pemeriksaan teks belum lulus')+' · '+(d.model||'model belum dilaporkan')+' · '+d.seconds+' dtk'}catch(e){box.textContent='Belum berhasil: '+e.message}};
$('#routerConnect').onclick=()=>loadAI().catch(sayError);
$('#useRouterModel').onclick=async()=>{try{await api('/api/router/model',{method:'POST',body:{model:$('#routerModel').value}});clearDraft($('#routerModel'));toast('Model aktif diganti');loadAI()}catch(e){sayError(e)}};
$('#providerForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/router/provider',{method:'POST',body:{provider:$('#apiProvider').value,apiKey:$('#providerKey').value,name:$('#providerName').value||$('#apiProvider').value}});$('#providerKey').value='';toast('Provider tersimpan');loadAI()}catch(e){sayError(e)}};
$('#comboForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/router/combo',{method:'POST',body:{name:$('#comboName').value,models:$('#comboModels').value.split('\n').map(x=>x.trim()).filter(Boolean)}});toast('Fallback dibuat');loadAI()}catch(e){sayError(e)}};
$('#oauthStart').onclick=async()=>{try{
  clearTimeout(oauthTimer);const d=await api('/api/router/oauth',{method:'POST',body:{provider:$('#oauthProvider').value,redirect_uri:$('#oauthRedirect').value}});oauthFlow=d;
  const u=new URL(d.url);if(u.protocol!=='https:'&&u.protocol!=='http:')throw Error('URL login tidak valid');
  $('#oauthLogin').href=u.href;$('#oauthLogin').classList.remove('hidden');$('#oauthInfo').textContent=d.user_code?'Kode login: '+d.user_code:'Setelah login, tempel URL callback lengkap. Jika localhost tidak terbuka, salin URL dari address bar.';
  $('#oauthCallbackRow').classList.toggle('hidden',d.device);if(d.device)oauthTimer=setTimeout(pollOAuth,d.interval*1000);
}catch(e){sayError(e)}};
async function pollOAuth(){try{const d=await api('/api/router/oauth/'+oauthFlow.flow,{method:'POST',body:{}});if(d.success){$('#oauthInfo').textContent='Akun berhasil terhubung.';oauthFlow=null;loadAI()}else if(d.pending){oauthFlow.interval=d.interval||oauthFlow.interval;oauthTimer=setTimeout(pollOAuth,oauthFlow.interval*1000)}else throw Error(d.error||'Login gagal')}catch(e){sayError(e)}}
$('#oauthFinish').onclick=async()=>{try{if(!oauthFlow)throw Error('Mulai login dahulu');const d=await api('/api/router/oauth/'+oauthFlow.flow,{method:'POST',body:{callback:$('#oauthCallback').value}});if(d.success){toast('Akun terhubung');$('#oauthCallback').value='';oauthFlow=null;loadAI()}else throw Error(d.error||'Login belum selesai')}catch(e){sayError(e)}};

function skillEditor(skill=null){editedSkill=skill;$('#skillEditor').classList.remove('hidden');$('#skillName').value=skill?.name||'';$('#skillWhen').value=skill?.when_to_use||'';$('#skillSteps').value=skill?.steps||'';$('#skillScope').innerHTML='<option value="shared">Semua bot</option>'+S.bots.map(b=>`<option value="${esc(b.id)}">${esc(b.name)}</option>`).join('');$('#skillScope').value=skill?.scope||'shared';$('#skillName').focus()}
$('#skillAdd').onclick=()=>skillEditor();$('#skillCancel').onclick=()=>$('#skillEditor').classList.add('hidden');
$('#skillEditor').onsubmit=async e=>{e.preventDefault();try{const body={name:$('#skillName').value,when_to_use:$('#skillWhen').value,steps:$('#skillSteps').value,scope:$('#skillScope').value};await api('/api/skills'+(editedSkill?'/'+editedSkill.id:''),{method:'POST',body});$('#skillEditor').classList.add('hidden');loadSkills();toast('Skill tersimpan')}catch(e){sayError(e)}};
$('#skillImport').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>16000)return toast('Skill terlalu panjang, maksimal 16 KB');const text=await file.text();skillEditor();const name=text.match(/^name:\s*(.+)$/m);const description=text.match(/^description:\s*(.+)$/m);$('#skillName').value=name?name[1].replace(/^['"]|['"]$/g,''):file.name.replace(/\.md$/,'');$('#skillWhen').value=description?description[1].replace(/^['"]|['"]$/g,''):'';$('#skillSteps').value=text.replace(/^---\s*\n[\s\S]*?\n---\s*\n/,'');e.target.value=''};

async function loadMCP(){const d=await api('/api/mcp');$('#mcpServers').innerHTML=d.servers.map(s=>`<div class="r"><div class="grow"><b>${esc(s.name)}</b><div class="sub">${esc(s.url||s.command)} · ${s.allow_tools.length} alat diizinkan</div></div><button class="btn sm" data-mcp-edit="${esc(s.name)}">Edit</button><button class="btn sm" data-mcp-delete="${esc(s.name)}">Hapus</button></div>`).join('')||empty('Belum ada MCP. Tambahkan server di bawah.');
 $$('[data-mcp-delete]').forEach(b=>b.onclick=async()=>{try{await api('/api/mcp/'+encodeURIComponent(b.dataset.mcpDelete),{method:'DELETE'});loadMCP();refreshBots()}catch(e){sayError(e)}});
 $$('[data-mcp-edit]').forEach(b=>b.onclick=()=>{const s=d.servers.find(s=>s.name===b.dataset.mcpEdit);$('#mcpName').value=s.name;$('#mcpUrl').value=s.url;$('#mcpCommand').value=s.command;$('#mcpArgs').value=JSON.stringify(s.args||[]);$('#mcpAllowed').value=s.allow_tools.join(', ');$('#mcpReadonly').value=s.read_only_tools.join(', ');$('#mcpToken').value='';$('#mcpKeepToken').checked=true;$('#mcpForm').scrollIntoView({behavior:'smooth'})});
 $('#mcpBot').innerHTML=S.bots.map(b=>`<option value="${esc(b.id)}">${esc(b.name)}</option>`).join('');
 $('#mcpTools').innerHTML=d.tools.map(t=>`<div class="r"><div class="grow">${esc(t.name)}<div class="sub">${esc(t.description)}</div></div><span class="pill">${t.approval?'Minta izin':'Baca saja'}</span></div>`).join('')||empty('Uji koneksi dan izinkan alat untuk mengaktifkannya.');}
function mcpBody(){const server={name:$('#mcpName').value,url:$('#mcpUrl').value,command:$('#mcpCommand').value,args:JSON.parse($('#mcpArgs').value||'[]'),allow_tools:$('#mcpAllowed').value.split(',').map(s=>s.trim()).filter(Boolean),read_only_tools:$('#mcpReadonly').value.split(',').map(s=>s.trim()).filter(Boolean),bot_id:$('#mcpBot').value};if(!$('#mcpKeepToken').checked)server.token=$('#mcpToken').value;return server}
$('#mcpDiscover').onclick=async()=>{try{const b=mcpBody();if(b.token)b.headers={Authorization:'Bearer '+b.token};const d=await api('/api/mcp/discover',{method:'POST',body:b});$('#mcpFound').textContent=d.tools.map(t=>t.name+' — '+(t.description||'')).join('\n');$('#mcpAllowed').value=d.tools.map(t=>t.name).join(', ');toast('Alat ditemukan. Tinjau daftar sebelum menyimpan.')}catch(e){sayError(e)}};
$('#mcpForm').onsubmit=async e=>{e.preventDefault();try{const d=await api('/api/mcp',{method:'POST',body:mcpBody()});$('#mcpToken').value='';toast(d.connection_errors?.length?'Konfigurasi disimpan, koneksi gagal: '+d.connection_errors.join(', '):'MCP tersimpan dan aktif');loadMCP();refreshBots()}catch(e){sayError(e)}};

async function loadUpdates(){const d=await api('/api/update');$('#updateVersion').textContent=d.version;$('#updateAuto').checked=d.auto;$('#updateStatus').textContent=d.message||'Belum ada pemeriksaan update.'}
$('#updateAuto').onchange=async e=>{try{await api('/api/update',{method:'POST',body:{auto:e.target.checked}});toast('Pengaturan update disimpan')}catch(e){sayError(e)}};
$('#updateCheck').onclick=async()=>{try{await api('/api/update',{method:'POST',body:{check:true}});toast('VPS akan memeriksa release dalam sekitar 30 detik.')}catch(e){sayError(e)}};
$('#updateInstall').onclick=async()=>{try{await api('/api/update',{method:'POST',body:{install:true}});toast('Update diminta. VPS akan membuat backup dan memasang release terbaru.')}catch(e){sayError(e)}};


async function showOfficeLog(bot,refresh=false){
 if(!refresh){openedOfficeLog=bot;logGeneration++;}
 const generation=logGeneration;
 try{const d=await api('/api/office/log/'+encodeURIComponent(bot));
 if(generation!==logGeneration||openedOfficeLog!==bot)return;
 $('#officeLog').classList.remove('hidden');
 $('#officeLogTitle').textContent='Log '+(S.bots.find(b=>b.id===bot)?.name||bot);
 const logRows=[...d.events.map(e=>({title:new Date(e.created_at*1000).toLocaleTimeString()+' · '+e.kind,text:e.text,trace:[]})),...d.entries.map(e=>({title:new Date(e.created_at*1000).toLocaleString()+' · '+e.channel,text:e.content,trace:e.trace||[]}))];
 stablePanel($('#officeLogEntries'),logRows.map((e,i)=>`<div class="log-event"><small>${esc(e.title)}</small><p class="office-task-summary">${esc(officeTaskSummary(e.text))}</p><button class="btn sm" data-log-read="${i}">Baca lengkap</button></div>`).join('')||empty('Belum ada aktivitas tercatat.'));
 $$('#officeLogEntries [data-log-read]').forEach(b=>b.onclick=()=>{const e=logRows[Number(b.dataset.logRead)];showDetail(e.title,'<pre class="detail-text">'+esc(e.text)+'</pre>'+e.trace.map(t=>'<h4>'+esc(t.tool)+'</h4><pre class="detail-text">'+esc(t.result)+'</pre>').join(''))});
 if(!refresh)$('#officeLog').scrollIntoView({block:'nearest'});
 }catch(e){if(generation===logGeneration)sayError(e)}
}
$('#officeLogClose').onclick=()=>{openedOfficeLog=null;logGeneration++;$('#officeLog').classList.add('hidden')};

async function loadLocalModels(){
 const d=await api('/api/local-models'), h=d.hardware, r=d.runtime;
 renderRuntime(r);
 const labels={queued:'Menunggu',preparing:'Menyiapkan',downloading:'Mengunduh',verifying:'Memeriksa SHA256',loading:'Memuat model',ready:'Siap',failed:'Gagal',stopped:'Tidak aktif'};
 const busy=['queued','preparing','downloading','verifying','loading'].includes(r.phase);
 $('#runtimePhase').textContent=labels[r.phase]||'Memeriksa';$('#runtimeStatus').textContent=r.message||'';
 $('#runtimeSpinner').classList.toggle('hidden',!busy);$('#runtimeProgress').classList.toggle('hidden',r.phase!=='downloading');
 const pct=r.total_bytes?Math.min(100,100*(r.downloaded_bytes||0)/r.total_bytes):0;
 $('#runtimeProgress').value=pct;$('#runtimeBytes').textContent=r.phase==='downloading'?`${pct.toFixed(1)}% · ${((r.downloaded_bytes||0)/1e6).toFixed(0)} / ${(r.total_bytes/1e6).toFixed(0)} MB`:r.ready?'Siap berarti server sudah merespons dan modelnya sesuai.':'';
 $('#runtimeLog').textContent=d.log||'Log muncul setelah mesin lokal dinyalakan. Log supervisor: agen supervisor-log';
 $('#hardwareSummary').textContent=h.source==='host'?`${(h.ram_mb/1024).toFixed(1)} GB RAM · ${(h.available_mb/1024).toFixed(1)} GB tersedia · ${h.cpus} CPU · ${h.architecture}`:'Hardware host belum tersedia. Supervisor VPS akan membacanya secara otomatis.';
 if(h.source==='host'&&!d.recommended)$('#hardwareSummary').textContent+=' · RAM tersedia belum cukup; gunakan API.';
 $('#localModelCards').innerHTML=d.models.map(m=>`<article class="model-card ${m.id===d.recommended?'recommended':''}"><div class="row"><b class="grow">${esc(m.name)}</b>${m.id===d.recommended?'<span class="pill">Rekomendasi</span>':''}</div><p>${esc(m.note)}</p><div class="hint">Unduh ${m.download_gb} GB · RAM ≥ ${m.min_ram_gb} GB · ${m.custom?"GGUF pilihan Anda":"Q4"} · teks</div><div class="row"><button class="btn sm" data-local-model="${esc(m.id)}" ${!m.fits||busy||r.ready&&m.id===d.selected?'disabled':''}>${busy&&m.id===d.selected?'Sedang diproses':r.ready&&m.id===d.selected?'Sudah siap':m.id===d.selected?'Unduh / perbaiki':'Pilih & unduh'}</button><a href="${esc(m.source)}" target="_blank" rel="noopener noreferrer">Detail model</a></div></article>`).join('');
 $$('[data-local-model]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const d=await api('/api/local-models',{method:'POST',body:{id:b.dataset.localModel}});toast(d.message);loadAI().catch(sayError)}catch(e){sayError(e);b.disabled=false}});
 if(typeof wireBusy==='function')wireBusy($('#v-ai'));
}
$('#refreshHardware').onclick=()=>loadLocalModels().catch(sayError);
$('#mcpGithubPreset').onclick=()=>{$('#mcpName').value='github';$('#mcpUrl').value='https://api.githubcopilot.com/mcp/';$('#mcpCommand').value='';$('#mcpArgs').value='[]';$('#mcpToken').value='';$('#mcpAllowed').value='';$('#mcpReadonly').value='';$('#mcpKeepToken').checked=false;$('#mcpForm').scrollIntoView({block:'start'});$('#mcpToken').focus();toast('Isi token GitHub lalu uji koneksi. Pilih alat baca saja yang diperlukan.')};

function askCorrection(){return new Promise(resolve=>{const dialog=$('#feedbackDialog');$('#feedbackNote').value='';dialog.onclose=()=>resolve(dialog.returnValue==='save'?$('#feedbackNote').value.trim():'');dialog.showModal();$('#feedbackNote').focus()})}


async function loadFree(generation=aiGeneration){try{
 const d=await api('/api/freellmapi');if(generation!==aiGeneration)return;$('#freeStatus').textContent='Terhubung. Strategi auto membutuhkan provider yang siap; kunci penghubung dikelola di server.';
 syncOptions($('#freeProvider'),d.providers.map(p=>({value:p.id,label:p.name+(p.keyless?' (tanpa key jika didukung)':'')})),'');
 syncOptions($('#freeModel'),d.models.map(m=>({value:m.id,label:(m.name||m.id)+' · '+m.id+' '+(m.status||'')})),d.active_model);
 $('#freeConnections').innerHTML=d.connections.map(c=>`<div class="r"><span class="grow">${esc(c.label||c.platform)} · ${esc(c.status||'belum diuji')}</span><button class="btn sm" data-free-delete="${c.id}">Hapus</button></div>`).join('')||empty('Tambahkan provider terlebih dahulu.');
 $$('[data-free-delete]').forEach(b=>b.onclick=async()=>{if(confirm('Hapus koneksi ini?')){try{await api('/api/freellmapi/provider/'+b.dataset.freeDelete,{method:'DELETE'});loadFree()}catch(e){sayError(e)}}});
 }catch(e){$('#freeStatus').textContent=e.message}}
$('#freeProviderForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/freellmapi/provider',{method:'POST',body:{platform:$('#freeProvider').value,key:$('#freeKey').value}});$('#freeKey').value='';toast('Provider ditambahkan');loadFree()}catch(e){sayError(e)}};
$('#useFreeModel').onclick=async()=>{try{await api('/api/freellmapi/model',{method:'POST',body:{model:$('#freeModel').value}});clearDraft($('#freeModel'));toast('Model aktif disimpan');loadAI()}catch(e){sayError(e)}};
async function loadBotModelChoices(){const backend=$('#botBackend').value;let models=[];try{
 if(backend==='router')models=(await api('/api/router')).models;
 else if(backend==='freellmapi')models=(await api('/api/freellmapi')).models;
 else if(backend==='local')models=(await api('/api/local-models')).models.map(m=>({id:m.id}));
 else if(backend==='online')models=[{id:(await api('/api/settings')).online_model}];
 $('#botModelChoices').innerHTML=models.filter(m=>m.id).map(m=>`<option value="${esc(m.id)}">${esc(m.name||m.id)}</option>`).join('');
 $('#botModelHint').textContent=backend==='local'?'Semua bot lokal berbagi satu model yang sedang dimuat. Ganti model lokal di Koneksi.':'Pilih model terhubung atau masukkan ID model yang tepat.';
 }catch(e){$('#botModelHint').textContent=e.message}}
$('#botBackend').onchange=()=>loadBotModelChoices().catch(sayError);

$('#directApiForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/settings',{method:'POST',body:{online_base:$('#directApiUrl').value,online_key:$('#directApiKey').value,online_model:$('#directApiModel').value}});clearDraft($('#directApiForm'));toast('API tersimpan');loadAI()}catch(e){sayError(e)}};
// Suspend polling while the page is hidden; refresh the active panel on return.
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(officeTimer);clearTimeout(aiTimer);clearTimeout(oauthTimer)}else{if(S.view==='office')loadOffice().catch(sayError);if(S.view==='ai')loadAI().catch(sayError);if(oauthFlow?.device)oauthTimer=setTimeout(pollOAuth,(oauthFlow.interval||5)*1000)}});



$('#openOfficeLog').onclick=()=>showOfficeLog($('#officeLogBot').value);

$('#clearAllOfficeHistory').onclick=async()=>{if(!confirm('Bersihkan semua aktivitas tersimpan dan log kantor? Tugas yang sedang berjalan tetap berjalan; source dan percakapan web/Telegram tetap ada.'))return;try{const d=await api('/api/office/history?scope=all',{method:'DELETE'});officeTasksFingerprint='';officeLearningFingerprint='';officeSpeech.clear();openedOfficeLog=null;logGeneration++;$('#officeLog').classList.add('hidden');toast(d.cleared+' aktivitas dibersihkan'+(d.working?' · '+d.working+' tugas masih berjalan':''));await loadOffice()}catch(e){sayError(e)}};

// Paginate records without removing stored data or hiding feature sections.
function recordPager(container,page,total,onChange){
 if(total<=8)return;
 const count=Math.ceil(total/8),nav=document.createElement('nav');nav.className='record-pagination';nav.setAttribute('aria-label','Halaman catatan');
 nav.innerHTML=`<button class="btn sm" ${page===0?'disabled':''}>Sebelumnya</button><span>${page+1} / ${count} · ${total} catatan</span><button class="btn sm" ${page===count-1?'disabled':''}>Berikutnya</button>`;
 const buttons=nav.querySelectorAll('button');buttons[0].onclick=()=>onChange(page-1);buttons[1].onclick=()=>onChange(page+1);container.append(nav);
}

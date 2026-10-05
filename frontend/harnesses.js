/* Lazy original runtimes. No background polling when hidden or idle. */
let harnessCatalog=null,harnessPoll=null,harnessFingerprint='';
const harnessMode=document.getElementById('harnessMode'),setupHarness=document.getElementById('setupHarness');
function harnessRow(id){return harnessCatalog?.items.find(x=>x.id===id)}
function harnessHints(){
 const row=harnessRow(harnessMode.value);document.getElementById('harnessHint').textContent=row?.description||'Mode lama tersimpan.';
 document.getElementById('setupHarnessHint').textContent=(harnessRow(setupHarness.value)?.description||'')+(harnessRow(setupHarness.value)?.kind?' Diunduh hanya saat setup disimpan. API key/model di Pengaturan → Harness.':'');
 const panel=document.getElementById('harnessRuntime');panel.classList.toggle('hidden',!row?.kind);if(!row?.kind)return;
 const r=row.runtime,busy=['queued','installing','preparing'].includes(r.phase),fp=JSON.stringify([row.id,r]);if(fp===harnessFingerprint)return;harnessFingerprint=fp;
 const same=panel.dataset.runtime===row.id,saved=same?Array.from(panel.querySelectorAll('input')).map(i=>[i.id,i.value]):[],opened=same&&panel.querySelector('details')?.open;panel.dataset.runtime=row.id;
 panel.innerHTML=`<div class="runtime-box" role="status"><span class="runtime-spinner ${busy?'':'hidden'}"></span><b>${esc({queued:'Menunggu',preparing:'Menyiapkan container',installing:'Memasang',installed:'Terpasang',failed:'Gagal',interrupted:'Terhenti',absent:'Belum terpasang'}[r.phase]||r.phase)}</b><p>${esc(r.message)}</p></div><div class="row"><button type="button" class="btn sm" id="harnessInstall" ${busy?'disabled':''}>${r.phase==='installed'?'Gunakan runtime':'Pasang & gunakan'}</button>${busy&&r.phase!=='preparing'?'<button type="button" class="btn sm" id="harnessCancel">Batalkan</button>':''}<a class="btn sm" href="${esc(row.source)}" target="_blank" rel="noopener">Panduan resmi</a></div>${r.phase==='failed'&&r.message.includes('Container terlalu kecil')?'<button type="button" class="btn sm" id="harnessPrepare">Siapkan RAM container & coba lagi</button>':''}<p class="hint">${esc(row.version)} · CLI asli, dipasang seperlunya. Container ≥ 2 GB. Izin, skill dan ingatan runtime terpisah.</p><details><summary>Model & kredensial runtime</summary><p class="hint">Runtime memerlukan akses penuh dan memakai alat sendiri. Izin alat per bot Agen Mini tidak membatasinya. Windows memakai izin akun Anda. Baca panduan resmi sebelum menjalankannya.</p><div class="field"><label for="runtimeModel">ID model asli</label><input id="runtimeModel" class="inp" value="${esc(r.model||'')}" placeholder="ID model sesuai panduan runtime"></div><div class="field"><label for="runtimeProvider">Provider (opsional)</label><input id="runtimeProvider" class="inp" value="${esc(r.provider||'')}"></div>${row.keys.map(k=>`<div class="field"><label for="runtime-${k}">${esc(k)}</label><input id="runtime-${k}" class="inp" type="${k.includes('KEY')?'password':'text'}" autocomplete="off" value="${esc(r.env?.[k]||'')}"></div>`).join('')}<button type="button" class="btn sm" id="harnessConfig">Simpan kredensial runtime</button><p class="hint">Tidak memakai login atau API key dari akun host. Isi hanya key milik Anda. Login OAuth native melalui terminal belum disediakan dalam web.</p></details>`;
 for(const [id,value] of saved){const input=document.getElementById(id);if(input)input.value=value}if(opened)panel.querySelector('details').open=true;
 document.getElementById('harnessInstall').onclick=()=>harnessAction('install',row.id);
 const prepare=document.getElementById('harnessPrepare');if(prepare)prepare.onclick=()=>prepareHarnessMemory(row.id);
 const cancel=document.getElementById('harnessCancel');if(cancel)cancel.onclick=()=>harnessAction('cancel',row.id);
 document.getElementById('harnessConfig').onclick=async()=>{const env={};row.keys.forEach(k=>env[k]=document.getElementById('runtime-'+k).value);try{await api('/api/harnesses',{method:'POST',body:{action:'configure',id:row.id,model:document.getElementById('runtimeModel').value,provider:document.getElementById('runtimeProvider').value,env}});toast('Konfigurasi tersimpan; uji dengan chat untuk memeriksa provider.');harnessFingerprint='';panel.dataset.runtime='';await loadHarnesses()}catch(e){sayError(e)}};
}
async function harnessAction(action,id){try{await api('/api/harnesses',{method:'POST',body:{action,id}});if(action==='install'){toast('Pilihan disimpan. Pemasangan berjalan di latar belakang.');await loadSettings()}harnessFingerprint='';await loadHarnesses()}catch(e){sayError(e)}}
async function loadHarnesses(){
 if(document.hidden)return;
 harnessCatalog=await api('/api/harnesses');
 for(const select of [harnessMode,setupHarness]){const old=select.value;for(const row of harnessCatalog.items){if(!Array.from(select.options).some(o=>o.value===row.id))select.add(new Option(row.name+' · runtime asli',row.id))}select.value=old;if(window.refreshDesignControls)refreshDesignControls()}
 harnessHints();clearTimeout(harnessPoll);harnessPoll=null;
 if(harnessCatalog.items.some(x=>['queued','installing','preparing'].includes(x.runtime.phase)))harnessPoll=setTimeout(()=>loadHarnesses().catch(sayError),4000);
}
harnessMode.addEventListener('change',()=>{harnessFingerprint='';harnessHints()});setupHarness.addEventListener('change',harnessHints);
document.getElementById('setupProfile').addEventListener('change',()=>{setupHarness.value=document.getElementById('setupProfile').value==='blank'?'none':'assisted';harnessHints();if(window.refreshDesignControls)refreshDesignControls()});
const originalLoadAI=loadAI;loadAI=async function(){await originalLoadAI();await loadHarnesses()};
const originalLoadSettings=loadSettings;loadSettings=async function(){await loadHarnesses();await originalLoadSettings();harnessHints();if(window.refreshDesignControls)refreshDesignControls()};
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(harnessPoll);harnessPoll=null}else if(harnessCatalog)loadHarnesses().catch(sayError)});
loadHarnesses().catch(()=>{});

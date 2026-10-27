'use strict';
const REPO='https://github.com/Zwart04/agenmini';
const list=document.querySelector('#download-list');
let assets=[],release=null,selectedOS=/Android|iPhone|iPad/i.test(navigator.userAgent)?'other':/Windows/i.test(navigator.userAgent)?'windows':/Macintosh|Mac OS X/i.test(navigator.userAgent)?'other':'linux',arch=/aarch64|arm64/i.test(navigator.userAgent)?'arm64':'amd64',timer;
function notice(message){const el=document.querySelector('#toast');el.textContent=message;el.hidden=false;clearTimeout(timer);timer=setTimeout(()=>{el.hidden=true;},4000);}
function asset(test){return assets.find(a=>test(a.name));}
function row(symbol,title,description,item,command){
 const card=document.createElement('article');card.className='package';
 const icon=document.createElement('span');icon.className='package-symbol';icon.textContent=symbol;icon.setAttribute('aria-hidden','true');
 const text=document.createElement('div'),h=document.createElement('h3'),p=document.createElement('p');h.textContent=title;p.textContent=description;text.append(h,p);
 let action;
 if(item){action=document.createElement('a');action.className='download-action';action.href=item.url;action.textContent='Download ↓';action.setAttribute('aria-label','Download '+title);if(command)action.addEventListener('click',()=>setCommand(command(item.name)));}
 else{action=document.createElement('span');action.className='unavailable';action.textContent='Belum ada pada rilis ini';}
 card.append(icon,text,action);list.append(card);
}
function setCommand(command){document.querySelector('#install-command').textContent=command;}
function safeRelease(value){
 if(!value||!/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(value.tag)||!Array.isArray(value.assets))throw Error('Metadata rilis tidak valid');
 return {tag:value.tag,assets:value.assets.filter(a=>a&&typeof a.name==='string'&&/^[a-zA-Z0-9._-]+$/.test(a.name)&&typeof a.url==='string'&&a.url.startsWith(REPO+'/releases/download/'+value.tag+'/')&&a.url.endsWith('/'+a.name))};
}
function render(){
 for(const button of document.querySelectorAll('[data-os]')){const selected=button.dataset.os===selectedOS;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;}
 for(const button of document.querySelectorAll('[data-arch]')){const selected=button.dataset.arch===arch;button.setAttribute('aria-pressed',String(selected));button.classList.toggle('selected',selected);}
 document.querySelector('.architecture').hidden=selectedOS!=='linux';document.querySelector('#download-panel').setAttribute('aria-labelledby','tab-'+selectedOS);
 list.replaceChildren();const summary=document.querySelector('#download-summary'),note=document.querySelector('#package-note');
 if(selectedOS==='linux'){
  summary.textContent='Pilih keluarga distro Anda. Setiap paket menyediakan ikon aplikasi dan perintah agenmini.';
  row('deb','Debian / Ubuntu / Mint','.deb · aplikasi + CLI',asset(n=>n.endsWith('_'+arch+'.deb')),n=>'sudo apt install ./'+n);
  row('rpm','Fedora / distro RPM','.rpm · aplikasi + CLI',asset(n=>n.endsWith('.'+(arch==='amd64'?'x86_64':'aarch64')+'.rpm')),n=>'sudo dnf install ./'+n);
  row('arch','Arch / EndeavourOS / Manjaro','.pkg.tar.zst · x86_64',arch==='amd64'?asset(n=>n.endsWith('.pkg.tar.zst')):null,n=>'sudo pacman -U ./'+n);
  row('tar','Linux lainnya / portable','.tar.gz · GNU/Linux glibc 2.35+',asset(n=>n.endsWith('-linux-'+arch+'.tar.gz')),n=>'tar -xzf '+n);
  note.textContent='Python privat dan gateway Go sudah disertakan. Paket distro memasang dependensi Node.js, Git dan xdg-utils melalui package manager. Portable memerlukan dependensi sistem itu. Arch tersedia untuk x86_64; ARM64 tersedia dalam .deb, .rpm dan portable. Paket ini unduhan langsung, bukan repositori distro atau AUR. Model AI tidak dibundel.';
  const first=asset(n=>n.endsWith('_'+arch+'.deb'));setCommand(first?'sudo apt install ./'+first.name:'agenmini --help');
 }else if(selectedOS==='windows'){
  summary.textContent='Windows 10 / 11 64-bit. Installer untuk sehari-hari, ZIP portable untuk aplikasi dan CLI tanpa pemasang.';
  row('exe','Windows installer','.exe · aplikasi desktop + agenmini.cmd',asset(n=>/^agenmini-setup-.*-windows-x64\.exe$/.test(n)));
  row('zip','Windows portable + CLI','.zip · ekstrak, lalu jalankan launcher / agenmini.cmd',asset(n=>/^agenmini-.*-windows-x64\.zip$/.test(n)));
  note.textContent='Data berada di akun Windows Anda, terpisah dari program. Pasang update pada lokasi yang sama. CLI: buka Start Menu → Agen Mini CLI, atau jalankan .\\agenmini.cmd dari folder portable. Kunci/provider/model tetap bisa diubah melalui Pengaturan.';setCommand('.\\agenmini.cmd model');
 }else{
  summary.textContent='macOS dan platform lain: gunakan source untuk menjalankan antarmuka web lokal dan CLI.';
  row('src','Source + CLI','Python 3.12, Node.js dan dependensi diperlukan',asset(n=>n==='agenmini-source.zip'));
  note.textContent='Belum tersedia installer native macOS, Android atau iOS. Antarmuka web Agen Mini di VPS dapat dibuka lewat browser perangkat tersebut. Source bukan installer satu klik.';setCommand('DATA_DIR="$HOME/.local/share/agenmini" python -m app.cli model');
 }
 const source=asset(n=>n==='agenmini-source.zip');if(source)document.querySelector('#source-download').href=source.url;
}
for(const button of document.querySelectorAll('[data-os]'))button.addEventListener('click',()=>{selectedOS=button.dataset.os;render();});
document.querySelector('.platform-tabs').addEventListener('keydown',event=>{
 const buttons=[...document.querySelectorAll('[data-os]')],index=buttons.indexOf(document.activeElement);if(index<0)return;
 let next;if(event.key==='ArrowRight')next=(index+1)%buttons.length;else if(event.key==='ArrowLeft')next=(index+buttons.length-1)%buttons.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else return;
 event.preventDefault();buttons[next].click();buttons[next].focus();
});
for(const button of document.querySelectorAll('[data-arch]'))button.addEventListener('click',()=>{arch=button.dataset.arch;render();});
for(const button of document.querySelectorAll('.faq button'))button.addEventListener('click',()=>{const open=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!open));button.querySelector('span').textContent=open?'+':'−';document.getElementById(button.getAttribute('aria-controls')).hidden=open;});
document.querySelector('#copy-command').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(document.querySelector('#install-command').textContent);notice('Perintah disalin. Verifikasi checksum sebelum memasang.');}catch{notice('Tidak bisa menyalin otomatis. Pilih teks perintah lalu salin.');}});
render();
fetch('release.json',{cache:'no-cache'}).then(response=>{if(!response.ok)throw Error('Metadata rilis tidak tersedia');return response.json();}).then(safeRelease).then(value=>{release=value;assets=value.assets;document.querySelector('#release-status').textContent='Rilis stabil '+value.tag;document.querySelector('#all-releases').href=REPO+'/releases/tag/'+value.tag;render();}).catch(()=>{document.querySelector('#release-status').textContent='Daftar unduhan belum termuat. Buka rilis resmi di GitHub.';notice('Daftar rilis tidak tersedia. Gunakan tautan semua berkas.');});

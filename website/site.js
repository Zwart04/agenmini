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
 else{action=document.createElement('span');action.className='unavailable';action.textContent='Not included in this release';}
 card.append(icon,text,action);list.append(card);
}
function setCommand(command){document.querySelector('#install-command').textContent=command;}
function safeRelease(value){
 if(!value||!/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(value.tag)||!Array.isArray(value.assets))throw Error('Invalid release metadata');
 return {tag:value.tag,assets:value.assets.filter(a=>a&&typeof a.name==='string'&&/^[a-zA-Z0-9._-]+$/.test(a.name)&&typeof a.url==='string'&&a.url.startsWith(REPO+'/releases/download/'+value.tag+'/')&&a.url.endsWith('/'+a.name))};
}
function render(){
 for(const button of document.querySelectorAll('[data-os]')){const selected=button.dataset.os===selectedOS;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;}
 for(const button of document.querySelectorAll('[data-arch]')){const selected=button.dataset.arch===arch;button.setAttribute('aria-pressed',String(selected));button.classList.toggle('selected',selected);}
 document.querySelector('.architecture').hidden=selectedOS!=='linux';document.querySelector('#download-panel').setAttribute('aria-labelledby','tab-'+selectedOS);
 list.replaceChildren();const summary=document.querySelector('#download-summary'),note=document.querySelector('#package-note');
 if(selectedOS==='linux'){
  summary.textContent='Choose your distribution. Each package includes an app menu entry and the agenmini command.';
  row('deb','Debian / Ubuntu / Mint','.deb · app + CLI',asset(n=>n.endsWith('_'+arch+'.deb')),n=>'sudo apt install ./'+n);
  row('rpm','Fedora / distro RPM','.rpm · app + CLI',asset(n=>n.endsWith('.'+(arch==='amd64'?'x86_64':'aarch64')+'.rpm')),n=>'sudo dnf install ./'+n);
  row('arch','Arch / EndeavourOS / Manjaro','.pkg.tar.zst · x86_64',arch==='amd64'?asset(n=>n.endsWith('.pkg.tar.zst')):null,n=>'sudo pacman -U ./'+n);
  row('tar','Other Linux / portable','.tar.gz · GNU/Linux glibc 2.35+',asset(n=>n.endsWith('-linux-'+arch+'.tar.gz')),n=>'tar -xzf '+n);
  note.textContent='Private Python and the Go gateway are included. Distribution packages install Node.js, Git and xdg-utils through your package manager; portable installs need those system dependencies. Arch is x86_64 only; ARM64 is available as .deb, .rpm and portable archives. These are direct downloads, not a distribution repository or AUR. Model weights are separate.';
  const first=asset(n=>n.endsWith('_'+arch+'.deb'));setCommand(first?'sudo apt install ./'+first.name:'agenmini --help');
 }else if(selectedOS==='windows'){
  summary.textContent='Windows 10 / 11 64-bit. Choose the installer for everyday use or extract the portable ZIP for the app and CLI.';
  row('exe','Windows installer','.exe · desktop app + agenmini.cmd',asset(n=>/^agenmini-setup-.*-windows-x64\.exe$/.test(n)));
  row('zip','Windows portable + CLI','.zip · extract, then run the launcher / agenmini.cmd',asset(n=>/^agenmini-.*-windows-x64\.zip$/.test(n)));
  note.textContent='Your data is stored in your Windows account, separately from the program. Install updates in the same location. CLI: open Start Menu → Agen Mini CLI, or run .\\agenmini.cmd from the portable folder. Change keys, providers and models in Settings.';setCommand('.\\agenmini.cmd model');
 }else{
  summary.textContent='macOS and other platforms: use source for the local web interface and CLI.';
  row('src','Source + CLI','Requires Python 3.12, Node.js and app dependencies',asset(n=>n==='agenmini-source.zip'));
  note.textContent='No native macOS, Android or iOS installer is available yet. You can also access your own Agen Mini VPS from those devices. Source requires manual setup.';setCommand('DATA_DIR="$HOME/.local/share/agenmini" python -m app.cli model');
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
document.querySelector('#copy-command').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(document.querySelector('#install-command').textContent);notice('Command copied. Verify the checksum before installing.');}catch{notice('Automatic copy is unavailable. Select and copy the command text.');}});
render();
fetch('release.json',{cache:'no-cache'}).then(response=>{if(!response.ok)throw Error('Release metadata is unavailable');return response.json();}).then(safeRelease).then(value=>{release=value;assets=value.assets;document.querySelector('#release-status').textContent='Stable release '+value.tag;document.querySelector('#all-releases').href=REPO+'/releases/tag/'+value.tag;render();}).catch(()=>{document.querySelector('#release-status').textContent='Downloads could not be loaded. Open the official GitHub release.';notice('The release list is unavailable. Use the all files link.');});

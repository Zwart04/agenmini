/* Original CSS characters. One observer, persistent nodes, no rendering loop. */
let officeSnapshot=null,officeRosterKey='',officeResizeObserver;
const officePalette=['#f6be89','#aecada','#c5b6e3','#afcdaa','#f0cc76','#e5adc0'];
const officeAccessories=['glasses','headphones','cap','sprout','scarf','bow'];
function officePlacement(d,width){
 const compact=width<600,cols=compact?2:3,rows=Math.ceil(d.bots.length/cols)||1;
 const height=Math.max(compact?540:400,rows*110+(compact?250:130));
 const meeting=new Set();
 (d.tasks||[]).filter(t=>t.status==='working'&&t.source!=='owner'&&d.bots.some(b=>b.id===t.source)&&d.bots.some(b=>b.id===t.target)).forEach(t=>{meeting.add(t.source);meeting.add(t.target)});
 const positions=d.bots.map((b,i)=>{
  const home={x:compact?(.23+(i%cols)*.5)*width:(.115+(i%cols)*.19)*width,y:80+Math.floor(i/cols)*110};
  let point=home,zone='Meja kerja';
  if(meeting.has(b.id)){
   const n=[...meeting].indexOf(b.id),count=meeting.size;
   point=compact?{x:width*(.11+(.38*(n+1)/(count+1))),y:height-125+(n%2)*48}:{x:width*(.67+.26*(n+1)/(count+1)),y:95+(n%3)*65+Math.floor(n/3)*24};zone='Ruang rapat';
  }else if(b.status==='waiting'||b.status==='queued'||(b.status==='working'&&b.phase==='queued')){
   point={x:compact?width*(.65+.19*(i%2)):width*(.73+.16*(i%2)),y:height-100-(i%3)*27};zone='Area tunggu';
  }
  point={...point,x:Math.max(43,Math.min(width-43,point.x))};
  return {id:b.id,home,point,zone};
 });
 return {positions,height,compact,meeting};
}
function officeStatus(b){return b.status==='working'?(b.action||'Sedang berpikir'):b.status==='waiting'?'Menunggu izin':b.status==='queued'?'Menunggu giliran':({done:'Tugas terakhir selesai',failed:'Tugas terakhir perlu perbaikan',waiting:'Menunggu izin'})[b.last_status]||'Siap membantu'}
function renderOfficeScene(d){
 d={...d,bots:[...d.bots].sort((a,b)=>(b.id==='orchestrator')-(a.id==='orchestrator'))};
 officeSnapshot=d;const room=$('#officeRoom');if(!room)return;
 const rosterKey=JSON.stringify(d.bots.map(b=>[b.id,b.name]));
 if(rosterKey!==officeRosterKey||!room.querySelector('.office-floor')){
  officeRosterKey=rosterKey;
  room.innerHTML='<div class="office-floor"><div class="office-window" aria-hidden="true"><i></i><i></i><i></i></div><span class="office-zone-title work-title">STUDIO KERJA</span><div class="office-meeting"><span class="office-zone-title">RUANG RAPAT</span><div class="meeting-table" aria-hidden="true"><i></i><i></i><i></i><i></i></div></div><div class="office-lounge"><span class="office-zone-title">AREA TUNGGU</span><div class="office-sofa" aria-hidden="true"></div><div class="office-plant" aria-hidden="true">✦</div></div><div class="office-furniture" aria-hidden="true"></div><div class="office-characters"></div></div>';
  const characters=room.querySelector('.office-characters'),furniture=room.querySelector('.office-furniture');
  d.bots.forEach((b,i)=>{
   const desk=document.createElement('div');desk.className='office-worktable';desk.dataset.desk=b.id;desk.innerHTML='<i class="office-monitor"></i><i class="office-keyboard"></i><i class="office-mug"></i>';furniture.append(desk);
   const node=document.createElement('button');node.type='button';node.className='office-character';node.dataset.bot=b.id;node.style.setProperty('--character-color',officePalette[i%6]);node.style.setProperty('--idle-delay',(-i*.8)+'s');node.innerHTML=`<span class="character-shadow"></span><span class="office-creature accessory-${officeAccessories[i%6]}"><span class="creature-face"><i class="creature-eye"></i><i class="creature-eye"></i><i class="creature-mouth"></i><i class="creature-cheek left"></i><i class="creature-cheek right"></i></span><i class="creature-accessory"></i><i class="creature-hands"></i></span><span class="character-name"></span><span class="character-activity"></span>`;node.onclick=()=>pickBot(b.id);characters.append(node);
  });
  $('#officeRoster').innerHTML=d.bots.map(b=>`<article class="office-member"><div><b>${esc(b.name)}</b><small data-presence="${esc(b.id)}"></small></div><button type="button" class="btn sm" data-log="${esc(b.id)}">Lihat log</button></article>`).join('');
  $$('#officeRoster [data-log]').forEach(b=>b.onclick=()=>showOfficeLog(b.dataset.log));
  if(!officeResizeObserver){officeResizeObserver=new ResizeObserver(()=>{if(officeSnapshot&&!document.hidden&&S.view==='office')positionOffice()});officeResizeObserver.observe(room)}
 }
 positionOffice();
}
function positionOffice(){
 const d=officeSnapshot,room=$('#officeRoom');if(!d||!room||document.hidden)return;
 const floor=room.querySelector('.office-floor'),width=room.clientWidth;if(!floor||!width)return;
 const layout=officePlacement(d,width);floor.style.height=layout.height+'px';floor.classList.toggle('compact',layout.compact);floor.classList.toggle('has-meeting',!!layout.meeting.size);
 const nodes=[...floor.querySelectorAll('[data-bot]')],desks=[...floor.querySelectorAll('[data-desk]')];
 layout.positions.forEach((p,i)=>{
  const b=d.bots[i],node=nodes[i];node.style.setProperty('--x',(p.point.x-30)+'px');node.style.setProperty('--y',(p.point.y-32)+'px');
  node.classList.toggle('is-working',b.status==='working');node.classList.toggle('is-meeting',layout.meeting.has(b.id));node.classList.toggle('is-tool',b.status==='working'&&['tool','writing'].includes(b.phase));node.classList.toggle('is-waiting',p.zone==='Area tunggu');
  const status=officeStatus(b);node.title=b.name+' · '+p.zone+' · '+status+(b.task?'\n'+b.task:'');node.setAttribute('aria-label',node.title+' · Buka chat');node.querySelector('.character-name').textContent=b.name;node.querySelector('.character-activity').textContent=b.status==='working'?(layout.meeting.has(b.id)?'Berdiskusi':b.phase==='tool'?'Memakai alat':'Bekerja'):p.zone==='Area tunggu'?'Menunggu':'Siap';
  const member=[...$('#officeRoster').querySelectorAll('[data-presence]')].find(n=>n.dataset.presence===b.id);if(member)member.textContent=p.zone+' · '+status;
  const desk=desks[i];desk.style.left=(p.home.x-37)+'px';desk.style.top=(p.home.y+20)+'px';
 });
}
function updateOfficePresence(ev){
 if(!officeSnapshot)return;const b=officeSnapshot.bots.find(b=>b.id===ev.bot);if(b)Object.assign(b,ev);
 // Tasks are fetched on the existing 5-second poll; presence changes arrive on SSE.
 if(!document.hidden&&S.view==='office')positionOffice();
}

function updateOfficeTask(ev){
 if(!officeSnapshot)return;
 const task=officeSnapshot.tasks.find(t=>t.id===ev.id);if(task)Object.assign(task,ev);else officeSnapshot.tasks.unshift(ev);
 if(!document.hidden&&S.view==='office')positionOffice();
}

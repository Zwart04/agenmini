/* Original CSS characters. One observer, persistent nodes, no rendering loop. */
let officeSnapshot=null,officeRosterKey='',officeResizeObserver,officeLayoutWidth=0;
const officeSpeech=new Map();
const officePalette=['#f6be89','#aecada','#c5b6e3','#afcdaa','#f0cc76','#e5adc0'];
const officeAccessories=['glasses','headphones','cap','sprout','scarf','bow'];
const teamNames={coordination:'Koordinasi',creative:'Kreatif',engineering:'Engineering',research:'Riset'};
const teamColors={coordination:'#eee2cf',creative:'#eee0e4',engineering:'#dbe8e5',research:'#e1e6d8'};
function officeBotTeam(b){return b.team||(['orchestrator','strategi'].includes(b.id)?'coordination':['desainer','copywriter'].includes(b.id)?'creative':['teknisi','reviewer'].includes(b.id)?'engineering':'research')}
function officePlacement(d,width){
 const compact=width<600,gap=14,roomWidth=compact?(width-42)/2:(width*.63-42)/2,cols=roomWidth>=290?3:roomWidth>=110?2:1;
 const keys=Object.keys(teamNames),groups=keys.map(key=>d.bots.filter(b=>officeBotTeam(b)===key));
 const roomHeights=groups.map(g=>70+Math.max(1,Math.ceil(g.length/cols))*116),rows=[Math.max(roomHeights[0],roomHeights[1]),Math.max(roomHeights[2],roomHeights[3])];
 const rooms=keys.map((key,i)=>({key,title:teamNames[key],color:teamColors[key],left:14+(i%2)*(roomWidth+gap),top:48+(i>=2?rows[0]+gap:0),width:roomWidth,height:rows[Math.floor(i/2)]}));
 const height=Math.max(compact?0:520,48+rows[0]+gap+rows[1]+(compact?218:26)),meeting=new Set();
 (d.tasks||[]).filter(t=>t.status==='working'&&t.source!=='owner'&&d.bots.some(b=>b.id===t.source)&&d.bots.some(b=>b.id===t.target)).forEach(t=>{meeting.add(t.source);meeting.add(t.target)});
 const positions=d.bots.map((b,i)=>{
  const index=keys.indexOf(officeBotTeam(b)),room=rooms[index<0?3:index],group=groups[index<0?3:index],slot=group.findIndex(x=>x.id===b.id);
  const home={x:room.left+room.width*(.5+(slot%cols))/cols,y:room.top+80+Math.floor(slot/cols)*116};let point=home,zone=room.title;
  if(meeting.has(b.id)){
   const n=[...meeting].indexOf(b.id),count=meeting.size;
   point=compact?{x:width*(.11+(.38*(n+1)/(count+1))),y:height-150+(n%2)*46}:{x:width*(.70+.24*(n+1)/(count+1)),y:95+(n%2)*100};zone='Ruang rapat';
  }else if(b.status==='waiting'||b.status==='queued'||(b.status==='working'&&b.phase==='queued')){
   point={x:compact?width*(.65+.19*(i%2)):width*(.73+.16*(i%2)),y:height-130-(i%3)*27};zone='Area tunggu';
  }
  point={...point,x:Math.max(43,Math.min(width-43,point.x))};return {id:b.id,home,point,zone};
 });return {positions,height,compact,meeting,rooms};
}

function officeStatus(b){return b.status==='working'?(b.action||'Sedang berpikir'):b.status==='waiting'?'Menunggu izin':b.status==='queued'?'Menunggu giliran':({done:'Tugas terakhir selesai',failed:'Tugas terakhir perlu perbaikan',waiting:'Menunggu izin'})[b.last_status]||'Siap membantu'}
function renderOfficeScene(d){
 d={...d,bots:[...d.bots].sort((a,b)=>(b.id==='orchestrator')-(a.id==='orchestrator'))};
 officeSnapshot=d;const room=$('#officeRoom');if(!room)return;
 const rosterKey=JSON.stringify(d.bots.map(b=>[b.id,b.name]));
 if(rosterKey!==officeRosterKey||!room.querySelector('.office-floor')){
  officeRosterKey=rosterKey;
  room.innerHTML='<div class="office-floor"><div class="office-window" aria-hidden="true"><i></i><i></i><i></i></div><span class="office-zone-title work-title">STUDIO KERJA</span><div class="office-meeting"><span class="office-zone-title">RUANG RAPAT</span><div class="meeting-table" aria-hidden="true"><i></i><i></i><i></i><i></i></div></div><div class="office-lounge"><span class="office-zone-title">AREA TUNGGU</span><div class="office-sofa" aria-hidden="true"></div><div class="office-plant" aria-hidden="true">✦</div></div><div class="office-team-rooms" aria-hidden="true"></div><div class="office-furniture" aria-hidden="true"></div><div class="office-characters"></div></div>';
  const characters=room.querySelector('.office-characters'),furniture=room.querySelector('.office-furniture');
  d.bots.forEach((b,i)=>{
   const desk=document.createElement('div');desk.className='office-worktable';desk.dataset.desk=b.id;desk.innerHTML='<i class="office-monitor"></i><i class="office-keyboard"></i><i class="office-mug"></i>';furniture.append(desk);
   const node=document.createElement('button');node.type='button';node.className='office-character';node.dataset.bot=b.id;node.style.setProperty('--character-color',officePalette[i%6]);node.style.setProperty('--idle-delay',(-i*.8)+'s');node.innerHTML=`<span class="character-bubble" aria-hidden="true"></span><span class="character-shadow"></span><span class="office-creature accessory-${officeAccessories[i%6]}"><span class="creature-face"><i class="creature-eye"></i><i class="creature-eye"></i><i class="creature-mouth"></i><i class="creature-cheek left"></i><i class="creature-cheek right"></i></span><i class="creature-accessory"></i><i class="creature-hands"></i></span><span class="character-name"></span><span class="character-activity"></span>`;node.onclick=()=>pickBot(b.id);characters.append(node);
  });
  if(!officeResizeObserver){officeResizeObserver=new ResizeObserver(()=>{if(officeSnapshot&&!document.hidden&&S.view==='office')positionOffice()});officeResizeObserver.observe(room)}
 }
 positionOffice();
}
function positionOffice(){
 const d=officeSnapshot,room=$('#officeRoom');if(!d||!room||document.hidden)return;
 const floor=room.querySelector('.office-floor'),width=room.clientWidth;if(!floor||!width)return;
 const resized=width!==officeLayoutWidth;officeLayoutWidth=width;if(resized)floor.classList.add('office-resized');
 const layout=officePlacement(d,width);floor.querySelector('.office-team-rooms').innerHTML=layout.rooms.map(r=>`<div class="office-team-room" style="left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;--room-color:${r.color}"><span>${esc(r.title)}</span><i class="team-room-mark"></i></div>`).join('');floor.style.height=layout.height+'px';floor.classList.toggle('compact',layout.compact);floor.classList.toggle('has-meeting',!!layout.meeting.size);
 const nodes=[...floor.querySelectorAll('[data-bot]')],desks=[...floor.querySelectorAll('[data-desk]')];
 layout.positions.forEach((p,i)=>{
  const b=d.bots[i],node=nodes[i];node.style.setProperty('--x',(p.point.x-30)+'px');node.style.setProperty('--y',(p.point.y-32)+'px');
  node.classList.toggle('is-working',b.status==='working');node.classList.toggle('is-meeting',layout.meeting.has(b.id));node.classList.toggle('is-tool',b.status==='working'&&['tool','writing'].includes(b.phase));node.classList.toggle('is-waiting',p.zone==='Area tunggu');
  const bubble=node.querySelector('.character-bubble'),speech=officeSpeech.get(b.id);
  const spoken=speech&&Date.now()/1000-speech.at<45,talking=b.status==='working',typing=talking&&!spoken;
  const text=spoken?speech.text:typing?(b.phase==='delegating'?'Mengajak diskusi':b.action||'Sedang berpikir'):'';
  const bubbleKey=JSON.stringify([typing,text,spoken?speech.at:0]);
  bubble.classList.toggle('visible',!!(talking||spoken));bubble.classList.toggle('typing',typing);bubble.classList.toggle('speaking',!!spoken);
  // Keep nodes intact during polling so animations can actually finish their cycles.
  if(bubble.dataset.message!==bubbleKey){bubble.dataset.message=bubbleKey;bubble.innerHTML=text?'<span>'+esc(text)+'</span><em class="bubble-dots" aria-hidden="true"><i></i><i></i><i></i></em>':'';}
  if(speech&&!spoken)officeSpeech.delete(b.id);
  const status=officeStatus(b);node.title=b.name+' · '+p.zone+' · '+status+(b.task?'\n'+b.task:'');node.setAttribute('aria-label',node.title+' · Buka chat');node.querySelector('.character-name').textContent=b.name;node.querySelector('.character-activity').textContent=b.status==='working'?(layout.meeting.has(b.id)?'Berdiskusi':b.phase==='tool'?'Memakai alat':'Bekerja'):p.zone==='Area tunggu'?'Menunggu':'Siap';
  const desk=desks[i];desk.style.left=(p.home.x-37)+'px';desk.style.top=(p.home.y+20)+'px';
 });
 if(resized){void floor.offsetWidth;floor.classList.remove('office-resized')}
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

function updateOfficeDiscussion(ev){
 if(!ev.bot||!ev.text)return;
 const at=Number(ev.created_at)||Date.now()/1000,previous=officeSpeech.get(ev.bot);
 if(!previous||at>=previous.at)officeSpeech.set(ev.bot,{text:ev.text,at});
 if(officeSnapshot&&!document.hidden&&S.view==='office')positionOffice();
}

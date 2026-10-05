/* Original CSS characters. One observer, persistent nodes, no rendering loop. */
let officeSnapshot=null,officeRosterKey='',officeResizeObserver,officeLayoutWidth=0;
const officeSpeech=new Map();
const officePalette=['#f6be89','#aecada','#c5b6e3','#afcdaa','#f0cc76','#e5adc0'];
const officeAccessories=['glasses','headphones','cap','sprout','scarf','bow'];
const teamNames={coordination:'Koordinasi',creative:'Kreatif',engineering:'Engineering',research:'Riset'};
const teamColors={coordination:'#eee2cf',creative:'#eee0e4',engineering:'#dbe8e5',research:'#e1e6d8'};
function officeBotTeam(b){const team=b.team||(['orchestrator','strategi'].includes(b.id)?'coordination':['desainer','copywriter'].includes(b.id)?'creative':['teknisi','reviewer'].includes(b.id)?'engineering':'research');return teamNames[team]?team:'research'}
function officePlacement(d,width){
 const compact=width<600,gap=14,roomWidth=(width*.63-42)/2,cols=roomWidth>=300?3:roomWidth>=190?2:1;
 const keys=Object.keys(teamNames),groups=keys.map(key=>d.bots.filter(b=>officeBotTeam(b)===key));
 const roomHeights=groups.map(g=>58+Math.max(1,Math.ceil(g.length/cols))*126),rows=[Math.max(roomHeights[0],roomHeights[1]),Math.max(roomHeights[2],roomHeights[3])];
 const rooms=compact?[]:keys.map((key,i)=>({key,title:teamNames[key],color:teamColors[key],left:14+(i%2)*(roomWidth+gap),top:24+(i>=2?rows[0]+gap:0),width:roomWidth,height:rows[Math.floor(i/2)]}));
 const meeting=new Set();
 (d.tasks||[]).filter(t=>t.status==='working'&&t.source!=='owner'&&d.bots.some(b=>b.id===t.source)&&d.bots.some(b=>b.id===t.target)).forEach(t=>{meeting.add(t.source);meeting.add(t.target)});
 const waiting=d.bots.filter(b=>!meeting.has(b.id)&&(b.status==='waiting'||b.status==='queued'||(b.status==='working'&&b.phase==='queued')));
 const mobileCols=width>=330?3:2,sideWidth=compact?width-28:width*.30-28,sideCols=Math.max(1,Math.floor(sideWidth/96));
 const meetingHeight=Math.max(184,64+Math.ceil(meeting.size/sideCols)*126),waitingHeight=Math.max(170,64+Math.ceil(waiting.length/sideCols)*126);
 const studioHeight=compact?30+Math.ceil(d.bots.length/mobileCols)*126:24+rows[0]+gap+rows[1];
 const height=compact?studioHeight+((meeting.size||waiting.length)?meetingHeight+waitingHeight+28:14):Math.max(studioHeight+24,meetingHeight+waitingHeight+52);
 const positions=d.bots.map((b,i)=>{
  const index=keys.indexOf(officeBotTeam(b)),group=groups[index<0?3:index],slot=group.findIndex(x=>x.id===b.id),room=rooms[index<0?3:index];
  const home=compact?{x:14+(width-28)*(i%mobileCols+.5)/mobileCols,y:52+Math.floor(i/mobileCols)*126}:{x:room.left+room.width*(.5+(slot%cols))/cols,y:room.top+66+Math.floor(slot/cols)*126};
  let point=home,zone=compact?teamNames[officeBotTeam(b)]||teamNames.research:room.title;
  const sideX=n=>compact?14+sideWidth*(.5+(n%sideCols))/sideCols:width*.66+sideWidth*(.5+(n%sideCols))/sideCols;
  if(meeting.has(b.id)){
   const n=[...meeting].indexOf(b.id);point={x:sideX(n),y:(compact?studioHeight+64:90)+Math.floor(n/sideCols)*126};zone='Ruang rapat';
  }else if(waiting.some(x=>x.id===b.id)){
   const n=waiting.findIndex(x=>x.id===b.id);point={x:sideX(n),y:(compact?studioHeight+meetingHeight+76:meetingHeight+100)+Math.floor(n/sideCols)*126};zone='Area tunggu';
  }
  point={...point,x:Math.max(43,Math.min(width-43,point.x))};return {id:b.id,home,point,zone};
 });return {positions,height,compact,meeting,rooms,meetingHeight,waitingHeight,studioHeight,hasSide:!!(meeting.size||waiting.length)};
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
   const node=document.createElement('button');node.type='button';node.className='office-character shape-'+['round','triangle','square','cloud','star','flame'][i%6];node.dataset.bot=b.id;node.style.setProperty('--character-color',officePalette[i%6]);node.style.setProperty('--idle-delay',(-i*.8)+'s');node.innerHTML=`<span class="character-bubble" aria-hidden="true"></span><span class="character-shadow"></span><span class="office-creature accessory-${officeAccessories[i%6]}"><span class="creature-face"><i class="creature-eye"></i><i class="creature-eye"></i><i class="creature-mouth"></i><i class="creature-cheek left"></i><i class="creature-cheek right"></i></span><i class="creature-accessory"></i><i class="creature-hands"></i></span><span class="character-name"></span><span class="character-activity"></span>`;node.onclick=()=>pickBot(b.id);characters.append(node);
  });
  if(!officeResizeObserver){officeResizeObserver=new ResizeObserver(()=>{if(officeSnapshot&&!document.hidden&&S.view==='office')positionOffice()});officeResizeObserver.observe(room)}
 }
 positionOffice();
}
function positionOffice(){
 const d=officeSnapshot,room=$('#officeRoom');if(!d||!room||document.hidden)return;
 const floor=room.querySelector('.office-floor'),width=room.clientWidth;if(!floor||!width)return;
 const resized=width!==officeLayoutWidth;officeLayoutWidth=width;if(resized)floor.classList.add('office-resized');
 const layout=officePlacement(d,width);floor.querySelector('.office-team-rooms').innerHTML=layout.rooms.map(r=>`<div class="office-team-room" style="left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;--room-color:${r.color}"><span>${esc(r.title)}</span><i class="team-room-mark"></i></div>`).join('');floor.style.height=layout.height+'px';floor.classList.toggle('compact',layout.compact);floor.classList.toggle('has-meeting',!!layout.meeting.size);floor.classList.toggle('has-side',layout.hasSide);const meetingRoom=floor.querySelector('.office-meeting'),lounge=floor.querySelector('.office-lounge');meetingRoom.style.top=(layout.compact?layout.studioHeight+14:24)+'px';meetingRoom.style.height=layout.meetingHeight+'px';lounge.style.top=(layout.compact?layout.studioHeight+layout.meetingHeight+28:layout.meetingHeight+38)+'px';lounge.style.height=layout.waitingHeight+'px';
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
  const status=officeStatus(b);node.title=b.name+' · '+p.zone+' · '+status+(b.task?'\n'+b.task:'');node.setAttribute('aria-label',node.title+' · Buka chat');node.querySelector('.character-name').textContent=b.name;node.querySelector('.character-activity').textContent=b.status==='working'?(layout.meeting.has(b.id)?'Berdiskusi':b.phase==='tool'?'Memakai alat':b.phase==='delegating'?'Delegasi':'Berpikir'):p.zone==='Area tunggu'?'Menunggu':'Siap';
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

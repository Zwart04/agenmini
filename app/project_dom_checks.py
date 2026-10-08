"""Minimal DOM contracts for model output; not shipped in generated apps."""
DOM_SETUP = r'''
function node(tag='div'){
  let ownText='';
  return {tagName:tag.toUpperCase(),className:'',style:{},children:[],attributes:{},
    set textContent(value){ownText=String(value);this.children=[];},
    get textContent(){return ownText+this.children.map(child=>child.textContent).join('');},
    get classList(){
      const element=this, tokens=()=>element.className.split(/\s+/).filter(Boolean);
      return {
        add(...names){element.className=[...new Set([...tokens(),...names])].join(' ');},
        remove(...names){element.className=tokens().filter(name=>!names.includes(name)).join(' ');},
        contains(name){return tokens().includes(name);},
        toggle(name,force){const enabled=force===undefined?!this.contains(name):!!force;if(enabled)this.add(name);else this.remove(name);return enabled;}
      };
    },
    set innerText(value){this.textContent=value;},
    get innerText(){return this.textContent;},
    set innerHTML(value){throw new Error('Timeline must use textContent, not innerHTML, for imported/user text');},
    appendChild(child){this.children.push(child);return child;},
    append(...children){children.forEach(child=>this.appendChild(child));},
    replaceChildren(...children){ownText='';this.children=[...children];},
    setAttribute(key,value){this.attributes[key]=String(value);if(key==='class')this.className=String(value);}
  };
}
function isElement(value){return !!value&&typeof value==='object'&&typeof value.tagName==='string'&&value.style&&typeof value.appendChild==='function';}
function percentage(value,expected){const text=String(value).trim();return /^[+-]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)(?:e[+-]?[0-9]+)?%$/i.test(text)&&Number(text.slice(0,-1))===expected;}
function mentionsNumber(text,expected){const values=String(text).match(/[+-]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)(?:e[+-]?[0-9]+)?/gi)||[];return values.some(value=>Number(value)===expected);}
function descendants(root){return root.children.flatMap(child=>[child,...descendants(child)]);}
function withClass(root,name){return descendants(root).filter(child=>child.className.split(/\s+/).includes(name));}
function formatTime(seconds){return 'time:'+seconds;}
document.createElement=node;
ui.timeline=node();ui.titleInput={value:''};ui.preview={currentTime:0};
'''
TIMELINE_CASE = DOM_SETUP + r'''
app.loaded=false;updateTimeline();
assert(ui.timeline.textContent.trim().length>0,'unloaded timeline must show an import-video message; actual='+JSON.stringify(ui.timeline.textContent));
app.loaded=true;app.duration=10;app.start=2;app.end=6;app.filename='<img src=x onerror=alert(1)>';
ui.titleInput.value='<b>Caption</b>';ui.preview.currentTime=4;
let priorCount=0;
for(let pass=0;pass<2;pass++){
  updateTimeline();const all=descendants(ui.timeline);
  assert(ui.timeline.children.length===3,'loaded timeline must have exactly one ruler and two tracks; actual root children='+ui.timeline.children.length);
  assert(withClass(ui.timeline,'track-row').length===2,'timeline must render two track rows');
  assert(JSON.stringify(withClass(ui.timeline,'track-label').map(label=>label.textContent))===JSON.stringify(['Video','Text']),'track labels must identify Video and Text');
  assert(withClass(ui.timeline,'track-lane').length===2,'timeline must render two track lanes');
  const video=withClass(ui.timeline,'video-clip');
  assert(video.length===1,'timeline must render one video clip');
  if(video.length){
    assert(percentage(video[0].style.left,20)&&percentage(video[0].style.width,40),'video clip position/width must reflect selected trim percentages');
    assert(video[0].textContent.includes(app.filename),'filename must be preserved as literal text');
  }
  const text=withClass(ui.timeline,'text-clip');
  assert(text.length===1&&text[0].textContent.includes(ui.titleInput.value),'caption must be preserved as literal text');
  const heads=withClass(ui.timeline,'playhead');
  assert(heads.length===2&&heads.every(head=>percentage(head.style.left,40)),'each lane needs an accurately positioned playhead');
  const rulers=withClass(ui.timeline,'timeline-ruler');
  assert(rulers.length===1&&rulers[0].textContent.includes(formatTime(10)),'timeline must have one ruler displaying actual formatted duration; actual='+JSON.stringify(rulers.map(ruler=>ruler.textContent)));
  assert(Number(ui.seekInput.value)===4,'timeline must synchronize scrub control');
  if(pass)assert(all.length===priorCount,'repeated rendering must replace old nodes, not accumulate them');
  priorCount=all.length;
}
ui.titleInput.value='';updateTimeline();
assert(withClass(ui.timeline,'text-clip').length===0,'empty caption must remove its timeline clip');
app.loaded=false;updateTimeline();
assert(withClass(ui.timeline,'track-row').length===0,'unloading must clear old tracks');
'''

DOM_CASES = {
 'video_timeline': TIMELINE_CASE,
 'timeline_element': DOM_SETUP + r'''
 for(const [tag,cls,text] of [['span','label','<img src=x>'],['div','clip','Caption']]){
   const result=makeTimelineElement(tag,cls,text);
   assert(isElement(result),'makeTimelineElement must return a DOM element; actual='+typeof result);if(isElement(result)){assert(result.tagName===tag.toUpperCase(),'element tag expected '+tag.toUpperCase()+'; actual='+result.tagName);assert(result.className===cls,'element className expected '+cls+'; actual='+JSON.stringify(result.className));assert(result.textContent===text,'element textContent expected literal '+JSON.stringify(text)+'; actual='+JSON.stringify(result.textContent));}
 }
 const first=makeTimelineElement('div','first','a'),second=makeTimelineElement('div','second','b');
 assert(first!==second&&first.textContent==='a','element creation must return independent nodes');
 ''',
 'timeline_playhead': DOM_SETUP + r'''
 app.duration=10;for(const time of [0,2.5,10]){ui.preview.currentTime=time;const head=makeTimelinePlayhead();assert(isElement(head),'makeTimelinePlayhead must return a DOM element, not a CSS value; actual='+JSON.stringify(head));if(isElement(head)){assert(head.className==='playhead','playhead className expected playhead; actual='+JSON.stringify(head.className));assert(percentage(head.style.left,time*10),'playhead left expected '+(time*10)+'% for currentTime='+time+' duration=10; actual='+JSON.stringify(head.style.left));}}
 ''',
 'timeline_percent': DOM_SETUP + r'''
 for(const duration of [8,10,30]){app.duration=duration;for(const seconds of [0,duration/4,duration,duration*1.5]){const actual=timelinePercent(seconds);assert(percentage(actual,seconds/duration*100),'timelinePercent must return percentage of full duration for seconds='+seconds+' duration='+duration+'; actual='+JSON.stringify(actual));}}
 ''',
 'timeline_selected_seconds': DOM_SETUP + r'''
 for(const [start,end] of [[0,10],[2.5,6.5],[1.25,3.75]]){app.start=start;app.end=end;const actual=timelineSelectedSeconds();assert(actual===end-start,'timelineSelectedSeconds must return numeric end minus start for start='+start+' end='+end+'; actual='+JSON.stringify(actual));}
 ''',
 'timeline_clip_bounds': DOM_SETUP + r'''
 for(const duration of [8,20])for(const [start,end] of [[0,duration],[duration/4,duration*0.75]]){
  app.duration=duration;app.start=start;app.end=end;const clip=node();clip.style.color='mint';clip.textContent='Keep label';
  const actual=setTimelineClipBounds(clip);
  assert(actual===clip,'setTimelineClipBounds must return the supplied element');
  assert(percentage(clip.style.left,start/duration*100),'clip bounds left must reflect start / duration; actual='+JSON.stringify(clip.style.left));
  assert(percentage(clip.style.width,(end-start)/duration*100),'clip bounds width must reflect selected duration; actual='+JSON.stringify(clip.style.width));
  assert(clip.style.color==='mint'&&clip.textContent==='Keep label','clip bounds must preserve other styles and text');
 }
 ''',
 'timeline_video_clip': DOM_SETUP + r'''
 app.filename='<img src=x>';for(const duration of [10,20])for(const [start,end] of [[0,duration],[duration/4,duration*0.65]]){app.duration=duration;app.start=start;app.end=end;const clip=makeTimelineVideoClip();assert(isElement(clip),'makeTimelineVideoClip must return a DOM element');if(isElement(clip)){assert(clip.tagName==='DIV','video clip must use a div element; actual='+clip.tagName);assert(clip.className==='video-clip','video clip className expected video-clip; actual='+JSON.stringify(clip.className));assert(percentage(clip.style.left,start/duration*100),'video clip left expected '+(start/duration*100)+'% for start='+start+' duration='+duration+'; actual='+JSON.stringify(clip.style.left));assert(percentage(clip.style.width,(end-start)/duration*100),'video clip width expected '+((end-start)/duration*100)+'% for start='+start+' end='+end+' duration='+duration+'; actual='+JSON.stringify(clip.style.width));assert(clip.textContent.includes(app.filename),'video clip must preserve literal filename; actual='+JSON.stringify(clip.textContent));assert(mentionsNumber(clip.textContent.replace(app.filename,''),end-start),'video clip must show selected seconds '+(end-start)+'; actual='+JSON.stringify(clip.textContent));}}
 ''',
 'timeline_text_clip': DOM_SETUP + r'''
 app.start=2;app.end=6;for(const duration of [10,20]){
  app.duration=duration;for(const value of ['', '   ']){ui.titleInput.value=value;assert(makeTimelineTextClip()===null,'empty caption must return null');}
  for(const value of ['<b>Caption</b>','  <b>Caption</b>  ']){
   ui.titleInput.value=value;const clip=makeTimelineTextClip();assert(isElement(clip),'caption clip must return a DOM element');if(!isElement(clip))continue;
   assert(clip.tagName==='DIV'&&clip.className==='text-clip','caption clip must use a div with class text-clip');
   assert(clip.textContent===value,'caption clip must preserve original literal text including surrounding spaces; actual='+JSON.stringify(clip.textContent));
   assert(percentage(clip.style.left,2/duration*100)&&percentage(clip.style.width,4/duration*100),'caption clip must follow trim bounds as CSS percentages for duration='+duration);
  }
 }
 ''',
 'timeline_track': DOM_SETUP + r'''
 app.duration=10;ui.preview.currentTime=3;
 for(const label of ['Video','Text'])for(const clip of [null,node()]){
  const row=makeTimelineTrack(label,clip);assert(row&&row.className==='track-row','track must return a row');if(!row)continue;
  const labels=withClass(row,'track-label'),lanes=withClass(row,'track-lane'),heads=withClass(row,'playhead');
  assert(labels.length===1&&labels[0].textContent===label,'track must have its requested label');
  assert(lanes.length===1,'track must have one lane');
  if(lanes.length)assert(lanes[0].children.length===(clip?2:1)&&(!clip||lanes[0].children.includes(clip)),'lane must contain supplied clip when present and a playhead');
  assert(heads.length===1&&percentage(heads[0].style.left,30),'track must include correctly positioned playhead');
 }
 '''
}

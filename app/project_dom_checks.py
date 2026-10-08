"""Minimal DOM contracts for model output; not shipped in generated apps."""
TIMELINE_CASE = r'''
function node(tag='div'){
  let ownText='';
  return {tagName:tag.toUpperCase(),className:'',style:{},children:[],attributes:{},
    set textContent(value){ownText=String(value);this.children=[];},
    get textContent(){return ownText+this.children.map(child=>child.textContent).join('');},
    set innerHTML(value){throw new Error('Timeline must use textContent, not innerHTML, for imported/user text');},
    appendChild(child){this.children.push(child);return child;},
    append(...children){children.forEach(child=>this.appendChild(child));},
    replaceChildren(...children){ownText='';this.children=[...children];},
    setAttribute(key,value){this.attributes[key]=String(value);}
  };
}
function descendants(root){return root.children.flatMap(child=>[child,...descendants(child)]);}
function withClass(root,name){return descendants(root).filter(child=>child.className.split(/\s+/).includes(name));}
function formatTime(seconds){return 'time:'+seconds;}
document.createElement=node;
ui.timeline=node();ui.titleInput={value:''};ui.preview={currentTime:0};
app.loaded=false;updateTimeline();
assert(ui.timeline.textContent.trim().length>0,'unloaded timeline must show an import-video message');
app.loaded=true;app.duration=10;app.start=2;app.end=6;app.filename='<img src=x onerror=alert(1)>';
ui.titleInput.value='<b>Caption</b>';ui.preview.currentTime=4;
let priorCount=0;
for(let pass=0;pass<2;pass++){
  updateTimeline();const all=descendants(ui.timeline);
  assert(withClass(ui.timeline,'track-row').length===2,'timeline must render two track rows');
  assert(JSON.stringify(withClass(ui.timeline,'track-label').map(label=>label.textContent))===JSON.stringify(['Video','Text']),'track labels must identify Video and Text');
  assert(withClass(ui.timeline,'track-lane').length===2,'timeline must render two track lanes');
  const video=withClass(ui.timeline,'video-clip');
  assert(video.length===1,'timeline must render one video clip');
  if(video.length){
    assert(parseFloat(video[0].style.left)===20&&parseFloat(video[0].style.width)===40,'video clip position/width must reflect selected trim percentages');
    assert(video[0].textContent.includes(app.filename),'filename must be preserved as literal text');
  }
  const text=withClass(ui.timeline,'text-clip');
  assert(text.length===1&&text[0].textContent.includes(ui.titleInput.value),'caption must be preserved as literal text');
  const heads=withClass(ui.timeline,'playhead');
  assert(heads.length===2&&heads.every(head=>parseFloat(head.style.left)===40),'each lane needs an accurately positioned playhead');
  assert(withClass(ui.timeline,'timeline-ruler').some(ruler=>ruler.textContent.includes(formatTime(10))),'ruler must display actual formatted duration');
  assert(Number(ui.seekInput.value)===4,'timeline must synchronize scrub control');
  if(pass)assert(all.length===priorCount,'repeated rendering must replace old nodes, not accumulate them');
  priorCount=all.length;
}
ui.titleInput.value='';updateTimeline();
assert(withClass(ui.timeline,'text-clip').length===0,'empty caption must remove its timeline clip');
app.loaded=false;updateTimeline();
assert(withClass(ui.timeline,'track-row').length===0,'unloading must clear old tracks');
'''

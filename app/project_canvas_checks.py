"""Small canvas API fixtures for model code; never shipped in generated apps."""

CANVAS_SETUP = r'''
const createdCanvases=[];let contextUnsupported=false;
function canvasContext(){
 const ctx={draws:[],fills:[],strokes:[],saved:[],font:'10px sans-serif',fillStyle:'#000',textAlign:'start',textBaseline:'alphabetic',shadowColor:'transparent',shadowBlur:0,strokeStyle:'#000',lineWidth:1,
  snapshot(){return Object.fromEntries(['font','fillStyle','textAlign','textBaseline','shadowColor','shadowBlur','strokeStyle','lineWidth'].map(key=>[key,this[key]]));},
  drawImage(...args){this.draws.push(args);},
  fillText(...args){this.fills.push({args,...this.snapshot()});},
  strokeText(...args){this.strokes.push({args,...this.snapshot()});},
  clearRect(){},save(){this.saved.push(this.snapshot());},restore(){Object.assign(this,this.saved.pop()||{});}
 };return ctx;
}
document.createElement=function(tag){
 if(tag!=='canvas')throw new Error('Expected detached canvas element, received '+tag);
 const canvas={width:300,height:150,_ctx:canvasContext(),getContext(kind){if(kind!=='2d')throw new Error('Expected 2d context');return contextUnsupported?null:this._ctx;}};
 createdCanvases.push(canvas);return canvas;
};
ui.preview={videoWidth:0,videoHeight:0};ui.titleInput={value:''};
function near(actual,expected){return typeof actual==='number'&&Number.isFinite(actual)&&Math.abs(actual-expected)<0.000001;}
function canvasColor(value){
 const text=String(value).trim().toLowerCase(),named={white:[255,255,255,1],black:[0,0,0,1],gray:[128,128,128,1],darkgray:[169,169,169,1],transparent:[0,0,0,0]};
 if(named[text])return named[text];
 if(/^#[0-9a-f]+$/.test(text)&&[4,5,7,9].includes(text.length)){
  let hex=text.slice(1);if(hex.length<=4)hex=[...hex].map(c=>c+c).join('');
  return [0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)).concat(hex.length===8?parseInt(hex.slice(6,8),16)/255:1);
 }
 const match=/^rgba?\((.+)\)$/.exec(text);if(!match)return null;
 const parts=match[1].trim().split(/[\s,/]+/);if(![3,4].includes(parts.length))return null;
 const values=parts.map((part,i)=>part.endsWith('%')?Number(part.slice(0,-1))*(i===3?.01:2.55):Number(part));
 if(values.some(v=>!Number.isFinite(v)))return null;
 return values.slice(0,3).map(v=>Math.min(255,Math.max(0,v))).concat(parts.length===4?Math.min(1,Math.max(0,values[3])):1);
}
function darkColor(value){const color=canvasColor(value);return color&&color[3]>0&&color[0]*.2126+color[1]*.7152+color[2]*.0722<140;}
'''

CANVAS_CASES = {
 'video_caption_style': CANVAS_SETUP + r'''
 for(const width of [180,320,590,610,720,1019]){
  const ctx=canvasContext();configureCaptionStyle(ctx,width);const expectedSize=Math.max(14,Math.round(width/30)),color=canvasColor(ctx.fillStyle);
  assert(/(?:\b(?:bold|[6-9]00)\b)/.test(ctx.font)&&new RegExp('\\b'+expectedSize+'px\\b').test(ctx.font)&&/(?:system-ui|sans-serif)/.test(ctx.font),'ctx.font expected bold '+expectedSize+'px system font for width='+width+'; actual='+JSON.stringify(ctx.font));
  assert(color&&color.slice(0,3).every(v=>near(v,255))&&near(color[3],1),'caption style fill expected opaque white; actual='+JSON.stringify(ctx.fillStyle));
  assert(ctx.textAlign==='center'&&ctx.textBaseline==='middle','caption style must set center alignment and middle baseline');
  assert(ctx.shadowBlur>0&&darkColor(ctx.shadowColor),'caption style must set a dark nontransparent shadow with positive blur');
  assert(ctx.draws.length===0&&ctx.fills.length===0&&ctx.strokes.length===0,'caption style must configure properties only, without painting');
 }
 ''',
 'video_canvas_prepare': CANVAS_SETUP + r'''
 for(const [width,height] of [[320,180],[1601,900],[1920,1080],[300,900]]){
  ui.preview.videoWidth=width;ui.preview.videoHeight=height;const before=createdCanvases.length;prepareCanvas();
  const canvas=createdCanvases[createdCanvases.length-1],expectedWidth=Math.min(width,720),expectedHeight=Math.max(1,Math.round(height*expectedWidth/width));
  assert(createdCanvases.length===before+1,'prepareCanvas must create one detached canvas for each preparation');
  assert(app.canvas===canvas&&app.ctx===canvas._ctx,'prepareCanvas must store the actual canvas and its 2d context');
  assert(app.canvas&&app.canvas.width===expectedWidth,'canvas width expected '+expectedWidth+' for video width='+width+'; actual='+(app.canvas&&app.canvas.width));
  assert(app.canvas&&app.canvas.height===expectedHeight,'canvas height expected '+expectedHeight+' for video '+width+'x'+height+'; actual='+(app.canvas&&app.canvas.height));
 }
 for(const [width,height] of [[0,180],[320,0],[-1,180],[320,-1],[NaN,180],[320,NaN],[Infinity,180],[320,Infinity]]){
  ui.preview.videoWidth=width;ui.preview.videoHeight=height;const oldCanvas=app.canvas,oldCtx=app.ctx;let problem;
  try{prepareCanvas();}catch(error){problem=error;}
  assert(problem&&typeof problem.message==='string'&&problem.message.trim(),'prepareCanvas must reject invalid video dimensions '+width+'x'+height+' with a descriptive Error');
  assert(app.canvas===oldCanvas&&app.ctx===oldCtx,'invalid dimensions must preserve the prior canvas/context');
 }
 contextUnsupported=true;ui.preview.videoWidth=320;ui.preview.videoHeight=180;const oldCanvas=app.canvas,oldCtx=app.ctx;let problem;
 try{prepareCanvas();}catch(error){problem=error;}
 assert(problem&&typeof problem.message==='string'&&problem.message.trim(),'prepareCanvas must reject unsupported 2d context with a descriptive Error');
 assert(app.canvas===oldCanvas&&app.ctx===oldCtx,'unsupported context must preserve the prior canvas/context');
 ''',
 'video_canvas_frame': CANVAS_SETUP + r'''
 for(const [width,height] of [[320,180],[720,405]])for(const value of ['', '   ', '<b>Caption</b>', '  café 日本語  ']){
  app.canvas={width,height,toDataURL(){return 'data:image/png;base64,fixture';}};app.ctx=canvasContext();ui.preview.videoWidth=width;ui.preview.videoHeight=height;ui.preview.readyState=4;ui.preview.src='blob:original-video';ui.preview.currentTime=2;ui.titleInput.value=value;paintFrame();const ctx=app.ctx;
  assert(ctx.draws.length===1&&ctx.draws[0][0]===ui.preview&&JSON.stringify(ctx.draws[0].slice(1))===JSON.stringify([0,0,width,height]),'ctx.drawImage expected source ui.preview and rectangle 0,0,'+width+','+height+' exactly once, before checking caption; actual count='+ctx.draws.length+'; actual arguments='+JSON.stringify(ctx.draws.map(args=>[args[0]===ui.preview?'ui.preview':'other source',...args.slice(1)])));
  assert(ui.preview.src==='blob:original-video'&&ui.preview.currentTime===2&&ui.titleInput.value===value,'paintFrame must preserve video source/time and original input text');
  if(!value.trim()){assert(ctx.fills.length===0&&ctx.strokes.length===0,'paintFrame must omit whitespace-only captions');continue;}
  assert(ctx.fills.length===1,'paintFrame must paint one caption');if(ctx.fills.length!==1)continue;
  const fill=ctx.fills[0],expectedSize=Math.max(14,Math.round(width/30));
  assert(fill.args[0]===value,'export caption must preserve original literal text; actual='+JSON.stringify(fill.args[0]));
  assert(near(fill.args[1],width/2),'ctx.fillText x expected '+(width/2)+' as second argument; actual='+JSON.stringify(fill.args[1]));
  assert(near(fill.args[2],height*.9),'ctx.fillText y expected '+(height*.9)+' as third argument; actual='+JSON.stringify(fill.args[2]));
  assert(near(fill.args[3],width*.9),'ctx.fillText maxWidth expected '+(width*.9)+' as fourth argument; actual='+JSON.stringify(fill.args[3]));
  assert(fill.textAlign==='center'&&fill.textBaseline==='middle','export caption must use center alignment and middle baseline');
  assert(/(?:\b(?:bold|[6-9]00)\b)/.test(fill.font)&&new RegExp('\\b'+expectedSize+'px\\b').test(fill.font)&&/(?:system-ui|sans-serif)/.test(fill.font),'export caption font must be bold system font at '+expectedSize+'px; actual='+JSON.stringify(fill.font));
  const color=canvasColor(fill.fillStyle);
  assert(color&&color.slice(0,3).every(v=>near(v,255))&&near(color[3],1),'export caption must use opaque white fill; actual='+JSON.stringify(fill.fillStyle));
  const outlined=ctx.strokes.some(stroke=>stroke.args[0]===value&&near(stroke.args[1],width/2)&&near(stroke.args[2],height*.9)&&stroke.lineWidth>0&&darkColor(stroke.strokeStyle));
  assert(outlined||fill.shadowBlur>0&&darkColor(fill.shadowColor),'export caption needs a dark contrast outline or shadow');
 }
 '''
}

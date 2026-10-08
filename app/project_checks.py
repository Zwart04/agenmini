"""Bounded behavioral checks for model source; never included in generated apps.

These small fixtures catch incorrect helpers before a full browser evaluation.
They are not a browser, and passing them cannot prove import/export behavior.
"""
import json
from . import tools

CHECKS = {'time_format', 'normalize_seconds', 'seconds_clock', 'status', 'busy', 'release_urls', 'video_load_error', 'video_file', 'video_callbacks', 'video_source', 'video_playback', 'video_seek', 'video_play_started', 'video_play_failed', 'video_start', 'video_pause', 'trim_range', 'trim_apply', 'trim_reject', 'video_trim'}
RUNNER = r'''
const vm = require('node:vm');
let input=''; process.stdin.on('data',b=>input+=b);
process.stdin.on('end',()=>{
  try {
    const {source,check}=JSON.parse(input);
    const context=vm.createContext(Object.create(null),{codeGeneration:{strings:false,wasm:false},microtaskMode:'afterEvaluate'});
    const fixtures=`"use strict";
      const app={loaded:false,busy:false};
      const ui={};
      for(const id of ['fileInput','playBtn','seekInput','startInput','endInput','exportBtn','cancelBtn','status']){
        const classes=new Set();
        ui[id]={disabled:false,hidden:false,textContent:'',classList:{
          toggle(name,force){const enabled=force===undefined?!classes.has(name):!!force; if(enabled)classes.add(name);else classes.delete(name);return enabled;},
          add(...names){for(const name of names)classes.add(name);},
          remove(...names){for(const name of names)classes.delete(name);},
          contains(name){return classes.has(name);}
        }};
        globalThis[id]=ui[id];
      }
      const document={getElementById(id){return ui[id]||null;},querySelector(selector){return selector.startsWith('#')?ui[selector.slice(1)]||null:null;}};
      const failures=[];
      function assert(value,message){if(!value)failures.push(message);}
    `;

    const playbackFixtures=`
      const calls={play:0,pause:0,timeline:0,errors:[]};
      ui.preview={paused:true,currentTime:0,rejectPlay:false,
        play(){calls.play++;if(this.rejectPlay)return Promise.reject(new Error('Decoder refused playback'));this.paused=false;return Promise.resolve();},
        pause(){calls.pause++;this.paused=true;}};
      function setStatus(message,error){calls.errors.push([message,error]);}
      function updateTimeline(){calls.timeline++;}
    `;
    const playbackCases=`
      for(const [loaded,busy] of [[false,false],[false,true],[true,true]]){
        app.loaded=loaded;app.busy=busy;ui.preview.paused=true;ui.preview.currentTime=7;
        const before=[calls.play,calls.pause,ui.preview.currentTime];await togglePlay();
        assert(JSON.stringify(before)===JSON.stringify([calls.play,calls.pause,ui.preview.currentTime]),'togglePlay must not play, pause or seek while unloaded or busy');
      }
      app.loaded=true;app.busy=false;app.start=2;app.end=8;app.duration=10;
      for(const time of [0,2,5,8,9]){
        ui.preview.paused=true;ui.preview.currentTime=time;const plays=calls.play;const pauses=calls.pause;
        await togglePlay();
        assert(calls.play===plays+1&&calls.pause===pauses,'paused video must call play once, never pause');
        assert(ui.preview.currentTime===(time<2||time>=8?2:time),'play must seek to trim start only when outside [start,end)');
        assert(ui.playBtn.textContent==='Pause','successful play must display Pause');
      }
      ui.preview.paused=false;ui.preview.currentTime=5;const pauses=calls.pause;const plays=calls.play;
      await togglePlay();assert(calls.pause===pauses+1&&calls.play===plays,'playing video must pause once, never play');
      assert(ui.playBtn.textContent==='Play','paused video must display Play');
      ui.preview.paused=true;ui.preview.rejectPlay=true;calls.errors.length=0;
      try{await togglePlay();}catch(error){assert(false,'togglePlay must catch preview.play() rejection instead of throwing: '+error.message);}assert(ui.playBtn.textContent==='Play','rejected play must restore Play label');
      assert(calls.errors.some(([message,error])=>error===true&&String(message).includes('Decoder refused playback')),'rejected play must report the actual error');
    `;


    const startCases=`
      app.loaded=true;app.busy=false;app.start=2;app.end=8;app.duration=10;
      for(const time of [0,2,5,8,9]){
        ui.preview.paused=true;ui.preview.currentTime=time;const plays=calls.play;const pauses=calls.pause;
        await startPlayback();
        assert(calls.play===plays+1&&calls.pause===pauses,'startPlayback must call play once without pausing');
        assert(ui.preview.currentTime===(time<2||time>=8?2:time),'startPlayback must seek to trim start only outside [start,end)');
        assert(ui.playBtn.textContent==='Pause','startPlayback must invoke playbackStarted on success');
      }
      ui.preview.paused=true;ui.preview.rejectPlay=true;calls.errors.length=0;
      try{await startPlayback();}catch(error){assert(false,'startPlayback must handle rejected preview.play() through playbackFailed: '+error.message);}
      assert(ui.playBtn.textContent==='Play','rejected start must invoke playbackFailed');
      assert(calls.errors.some(([message,error])=>error===true&&String(message).includes('Decoder refused playback')),'startPlayback must pass actual rejection to playbackFailed');
    `;

    const cases={
      trim_range:`for(const [start,end,duration,expected] of [[0,10,10,true],[1.25,3.75,10,true],[9,10,10,true],[-1,2,10,false],[3,3,10,false],[4,2,10,false],[0,11,10,false],[0,1,0,false],[NaN,2,10,false],[0,NaN,10,false],[0,2,NaN,false],[0,2,Infinity,false],[-Infinity,2,10,false],[0,Infinity,10,false],['0',2,10,false],[0,'2',10,false],[0,2,'10',false],[null,2,10,false]]){const actual=isTrimRange(start,end,duration);assert(actual===expected,'isTrimRange('+[start,end,duration].map(v=>JSON.stringify(v)).join(',')+') expected Boolean '+expected+' [observed '+JSON.stringify(actual)+']');}`,
      trim_apply:`for(const busy of [false,true])for(const [start,end] of [[0,10],[1.25,3.75]]){app.busy=busy;app.start=4;app.end=5;const before=calls.timeline;calls.errors.length=0;assert(applyTrim(start,end)===true,'applyTrim must return Boolean true');assert(app.start===start&&app.end===end,'applyTrim must store the supplied start/end');assert(ui.exportBtn.disabled===busy,'applyTrim must disable export only while busy');assert(calls.timeline===before+1,'applyTrim must updateTimeline once');assert(calls.errors.length===1&&String(calls.errors[0][0]).includes(String(end-start))&&calls.errors[0][1]!==true,'applyTrim must report the selected numeric duration as success');}`,
      trim_reject:`app.start=1;app.end=8;app.loaded=true;app.busy=false;ui.exportBtn.disabled=false;assert(rejectTrim()===false,'rejectTrim must return Boolean false');assert(ui.exportBtn.disabled===true,'rejectTrim must disable export');assert(app.start===1&&app.end===8&&app.loaded===true&&app.busy===false,'rejectTrim must preserve existing state');assert(calls.timeline===0,'rejectTrim must preserve the previous timeline');assert(calls.errors.length===1&&String(calls.errors[0][0]).length>0&&calls.errors[0][1]===true,'rejectTrim must report an error');`,
      video_trim:`app.duration=10;app.loaded=true;for(const [start,end,valid] of [['0','10',true],['1.25','3.75',true],['-1','2',false],['3','3',false],['4','2',false],['0','11',false],['abc','2',false],['0','Infinity',false]])for(const busy of [false,true]){app.busy=busy;app.start=1;app.end=8;ui.startInput.value=start;ui.endInput.value=end;ui.exportBtn.disabled=false;const before=calls.timeline;calls.errors.length=0;const actual=validateTrim();assert(actual===valid,'validateTrim('+JSON.stringify([start,end])+') expected Boolean '+valid+' [observed '+JSON.stringify(actual)+']');if(valid){assert(app.start===Number(start)&&app.end===Number(end),'valid trim must store parsed seconds');assert(ui.exportBtn.disabled===busy,'valid trim must preserve busy restriction');assert(calls.timeline===before+1,'valid trim must update timeline once');}else{assert(app.start===1&&app.end===8,'invalid trim must preserve previous valid bounds');assert(ui.exportBtn.disabled===true,'invalid trim must disable export');assert(calls.timeline===before,'invalid trim must preserve timeline');assert(calls.errors.some(([,error])=>error===true),'invalid trim must report an error');}}`,
      video_play_started:`ui.playBtn.textContent='Play';playbackStarted();assert(ui.playBtn.textContent==='Pause','playbackStarted must show Pause');assert(calls.play===0&&calls.pause===0&&calls.errors.length===0,'playbackStarted must only update the label');`,
      video_play_failed:`for(const message of ['Decoder refused playback','Playback permission denied']){ui.playBtn.textContent='Pause';calls.errors.length=0;playbackFailed(new Error(message));assert(ui.playBtn.textContent==='Play','playbackFailed must restore Play');assert(calls.errors.length===1&&calls.errors[0][0]===message&&calls.errors[0][1]===true,'playbackFailed must call setStatus with actual error.message and true');}assert(calls.play===0&&calls.pause===0,'playbackFailed must not start or pause media');`,
      video_pause:`ui.preview.paused=false;ui.preview.currentTime=5;ui.playBtn.textContent='Pause';pausePlayback();assert(calls.pause===1&&calls.play===0,'pausePlayback must call preview.pause once without playing');assert(ui.playBtn.textContent==='Play','pausePlayback must display Play');assert(ui.preview.currentTime===5,'pausePlayback must preserve currentTime');`,
      video_seek:`app.duration=10;app.loaded=true;app.busy=false;for(const [value,expected] of [['0',0],['3.25',3.25],[-4,0],[25,10],[0,0],[7.2,7.2]]){ui.preview.currentTime=5;const before=calls.timeline;seekVideo(value);assert(ui.preview.currentTime===expected,'seekVideo('+JSON.stringify(value)+') expected currentTime '+expected+'; observed '+ui.preview.currentTime);assert(calls.timeline===before+1,'valid seek must call updateTimeline once');}for(const value of ['abc',NaN,Infinity,-Infinity]){ui.preview.currentTime=5;const before=calls.timeline;seekVideo(value);assert(ui.preview.currentTime===5&&calls.timeline===before,'non-finite seek must preserve time and timeline');}for(const [loaded,busy] of [[false,false],[false,true],[true,true]]){app.loaded=loaded;app.busy=busy;ui.preview.currentTime=5;const before=calls.timeline;seekVideo(1);assert(ui.preview.currentTime===5&&calls.timeline===before,'unloaded/busy seek must not change time or timeline');}`,
      video_file:`for(const file of [null,undefined,{},0,true,'video/mp4',{type:null},{type:42},{type:''},{type:'image/png'},{type:'audio/webm'},{type:'VIDEO/MP4'}])assert(isVideoFile(file)===false,'isVideoFile('+JSON.stringify(file)+') expected Boolean false [observed '+JSON.stringify(isVideoFile(file))+']');for(const type of ['video/mp4','video/webm','video/quicktime']){const file={type,name:'actual clip'};assert(isVideoFile(file)===true,'isVideoFile('+JSON.stringify(file)+') expected Boolean true [observed '+JSON.stringify(isVideoFile(file))+']');assert(file.type===type&&file.name==='actual clip','isVideoFile must preserve file');}`,
      video_callbacks:`let calls=0;function videoMetadataReady(){calls++;}function videoLoadFailed(){calls++;}ui.preview={};attachVideoHandlers();assert(ui.preview.onloadedmetadata===videoMetadataReady,'preview.onloadedmetadata must hold videoMetadataReady reference');assert(ui.preview.onerror===videoLoadFailed,'preview.onerror must hold videoLoadFailed reference');assert(calls===0,'attachVideoHandlers must not call callbacks');`,
      video_source:`const created=[];const URL={createObjectURL(file){created.push(file);return 'blob:new-'+created.length;}};ui.preview={};ui.downloadLink={hidden:false};for(const name of ['clip A.mp4','clip <unsafe>.webm']){const file={type:'video/mp4',name};app.loaded=true;app.busy=false;ui.downloadLink.hidden=false;setVideoSource(file);assert(created[created.length-1]===file,'createObjectURL must receive the actual File argument');assert(app.objectURL==='blob:new-'+created.length&&ui.preview.src===app.objectURL,'preview.src must use newly created object URL');assert(app.filename===name,'app.filename must come from file.name');assert(app.loaded===false&&app.busy===false,'setVideoSource must clear loaded without changing busy');assert(ui.downloadLink.hidden===true,'downloadLink must stay hidden until a new export');}assert(created.length===2,'createObjectURL must be called once per file');`,
      release_urls:`const revoked=[];const URL={revokeObjectURL(value){revoked.push(value);}};for(const [objectURL,downloadURL] of [['blob:a','blob:b'],['blob:a',null],[null,'blob:b'],[null,null]]){revoked.length=0;app.loaded=true;app.busy=true;app.objectURL=objectURL;app.downloadURL=downloadURL;releaseVideoUrls();assert(JSON.stringify(revoked.sort())===JSON.stringify([objectURL,downloadURL].filter(Boolean).sort()),'releaseVideoUrls must revoke each existing URL exactly once; actual='+JSON.stringify(revoked));assert(app.objectURL===null&&app.downloadURL===null,'releaseVideoUrls must clear both URL fields');assert(app.loaded===true&&app.busy===true,'releaseVideoUrls must preserve loaded/busy state');}`,
      video_load_error:`app.loaded=true;app.busy=true;videoLoadFailed();assert(app.loaded===false,'videoLoadFailed must clear app.loaded');assert(app.busy===false,'videoLoadFailed must clear busy using setBusy');assert(ui.status.textContent.length>0&&ui.status.classList.contains('error'),'videoLoadFailed must set a nonempty error status with error class');`,
      normalize_seconds:`for(const value of [NaN,Infinity,-Infinity,-1,-0.1,null,undefined,'65',{},true])assert(normalizeSeconds(value)===0,'normalizeSeconds invalid input '+String(value)+' must return 0');for(let i=0;i<41;i++){const value=(i*83+7)/3;const actual=normalizeSeconds(value);assert(actual===Math.floor(value),'normalizeSeconds('+value+') must return '+Math.floor(value)+' [observed '+JSON.stringify(actual)+']');}`,
      seconds_clock:`for(const total of [0,1,9,59,60,65,599,3599,3600,...Array.from({length:41},(_,i)=>i*83+7)]){const expected=String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0');const actual=secondsToClock(total);assert(actual===expected,'secondsToClock('+total+') must return '+expected+' [observed '+JSON.stringify(actual)+']');}`,
      time_format:`for(const [value,expected] of [[0,'00:00'],[65,'01:05'],[65.9,'01:05'],[-1,'00:00'],[NaN,'00:00'],[Infinity,'00:00'],[3599,'59:59']]) {const actual=formatTime(value);assert(actual===expected,'formatTime('+value+') must return '+expected+' [observed '+JSON.stringify(actual)+']');}for(let i=0;i<41;i++){const value=(i*83+7)/3;const total=Math.floor(value);const expected=String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0');const actual=formatTime(value);assert(actual===expected,'formatTime('+value+') must return '+expected+' [observed '+JSON.stringify(actual)+']');}`,
      status:`setStatus('failed',true);assert(ui.status.textContent==='failed'&&ui.status.classList.contains('error'),'Error text/class not set');setStatus('failed again',true);assert(ui.status.classList.contains('error'),'Repeated errors must keep error class');setStatus('ready');assert(ui.status.textContent==='ready'&&!ui.status.classList.contains('error'),'Success must clear previous error class');`,
      busy:`for(const loaded of [false,true])for(const flag of [false,true]){app.loaded=loaded;setBusy(flag);assert(app.loaded===loaded,'app.loaded expected '+loaded+'; preserve loaded state; actual='+app.loaded);assert(app.busy===flag,'app.busy expected '+flag+' when busy='+flag+' loaded='+loaded+'; actual='+app.busy);assert(ui.fileInput.disabled===flag,'fileInput.disabled expected '+flag+' when busy='+flag+' loaded='+loaded+'; actual='+ui.fileInput.disabled);for(const id of ['playBtn','seekInput','startInput','endInput','exportBtn'])assert(ui[id].disabled===(flag||!loaded),id+'.disabled expected '+(flag||!loaded)+' when busy='+flag+' loaded='+loaded+'; actual='+ui[id].disabled);assert(ui.cancelBtn.hidden===!flag,'cancelBtn.hidden expected '+!flag+' when busy='+flag+' loaded='+loaded+'; actual='+ui.cancelBtn.hidden);}`
    };
    if(!Object.hasOwn(cases,check)&&!['video_playback','video_start'].includes(check))throw new Error('Unknown behavioral check');
    let result;
    if(['video_playback','video_start'].includes(check)){
      vm.runInContext(fixtures+'\n'+playbackFixtures+'\n'+source+'\n(async()=>{'+(check==='video_start'?startCases:playbackCases)+"\nglobalThis.__helperResult=JSON.stringify([...new Set(failures)].slice(0,12));})().catch(error=>{globalThis.__helperResult=JSON.stringify({execution_error:'Playback threw: '+error.message});});",context,{timeout:500});
      result=vm.runInContext('globalThis.__helperResult',context,{timeout:500});
      if(typeof result!=='string')throw new Error('Playback did not settle with an immediately resolved or rejected play promise');
    }else{
      result=vm.runInContext(fixtures+'\n'+(['video_seek','video_play_started','video_play_failed','video_pause','trim_apply','trim_reject','video_trim'].includes(check)?playbackFixtures:'')+'\n'+source+'\n'+cases[check]+"\nJSON.stringify([...new Set(failures)].slice(0,12));",context,{timeout:500});
    }
    const failures=JSON.parse(result);
    if(!Array.isArray(failures))throw new Error(failures.execution_error||'Helper checks did not complete');
    if(failures.length){console.error(JSON.stringify({helper_failures:failures}));process.exitCode=1;return;}
    console.log('behavioral helper check passed');
  }catch(error){console.error(error.message);process.exitCode=1;}
});
'''


async def inspect_helper(source, check):
    if check not in CHECKS:
        raise ValueError('Unknown helper behavioral check')
    payload=json.dumps({'source':source,'check':check}).encode()
    # Fixed runner + untrusted data, through the existing project sandbox.
    # No fixture bytes are added to model output or delivered application files.
    import base64
    encoded=base64.b64encode(RUNNER.encode()).decode()
    loader="eval(Buffer.from('"+encoded+"','base64').toString('utf8'))"
    result=await tools._run_sandboxed(['node','-e',loader],timeout=5,stdin=payload,project=True)
    if result.startswith('[kode keluar 0]'):return []
    # Keep individual failing cases addressable. A repair must not solve one
    # case by breaking a previously passing case; exceptions remain failures.
    detail=result.split('\n',1)[1] if result.startswith('[kode keluar 1]\n') else result
    try:
        cases=json.loads(detail.strip()).get('helper_failures')
        if isinstance(cases,list) and all(isinstance(case,str) for case in cases):
            return ['Helper behavior failed: '+case for case in cases]
    except (ValueError,AttributeError):pass
    return ['Helper execution failed: '+case for case in detail[-1000:].strip().split('; ') if case]

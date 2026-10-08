"""Recorder API fixtures; evaluator-only, never supplied as application source."""

EXPORT_CASES = {
    'video_seek_timer_factory': r'''
      let job,callback,delay,handle,failed=[];
      function setTimeout(fn,ms){callback=fn;delay=ms;return handle;}const window={setTimeout};
      function failSeekJob(value,error){failed.push([value,error]);}
      for(handle of [0,37,311]){
        callback=null;delay=0;failed=[];job={video:{},timer:null,onSeeked:null};
        const result=makeSeekTimer(job);
        assert(result===handle,'makeSeekTimer return expected actual browser handle '+handle+'; observed '+String(result));
        assert(delay===5000&&typeof callback==='function','makeSeekTimer must schedule a function after 5000 milliseconds');
        assert(failed.length===0&&job.timer===null&&job.onSeeked===null,'timer factory must defer failure and leave job handles unchanged');
        if(typeof callback==='function')callback();
        assert(failed.length===1&&failed[0][0]===job&&failed[0][1] instanceof Error&&failed[0][1].message,'timer callback must fail original job once with descriptive Error');
      }
    ''',
    'video_seek_callback': r'''
      const completed=[];function completeSeekJob(job){completed.push(job);}
      const first={video:{}},second={video:{}};
      const one=makeSeekCallback(first),two=makeSeekCallback(second);
      assert(typeof one==='function'&&typeof two==='function'&&one!==two,'makeSeekCallback must return a new function for each original job');
      assert(completed.length===0,'makeSeekCallback must not complete during callback creation');
      if(typeof two==='function')two();if(typeof one==='function')one();
      assert(completed.length===2&&completed[0]===second&&completed[1]===first,'returned callback must complete exactly its original job when invoked');
    ''',
    'video_seek_store': r'''
      const calls=[];const callback=()=>{};let job;
      function makeSeekCallback(value){calls.push(value);return callback;}
      const video={},resolve=()=>{},reject=()=>{};
      job={video,resolve,reject,timer:null,onSeeked:null};storeSeekCallback(job);
      assert(calls.length===1&&calls[0]===job,'storeSeekCallback must create callback once using original job');
      assert(job.onSeeked===callback,'storeSeekCallback must assign actual factory result to job.onSeeked');
      assert(job.video===video&&job.resolve===resolve&&job.reject===reject&&job.timer===null,'storeSeekCallback must retain all other job properties');
    ''',
    'video_seek_listen': r'''
      const registered=[];let completed=0;const callback=()=>{completed++;};
      const video={addEventListener(name,fn){registered.push([name,fn]);}};
      const job={video,onSeeked:callback};listenSeekCallback(job);
      assert(registered.length===1&&registered[0][0]==='seeked','listenSeekCallback must register the seeked event exactly once');
      assert(registered.length===1&&registered[0][1]===callback,'Callback argument job.video.addEventListener expected job.onSeeked as original function reference; observed '+(registered.length?String(registered[0][1]):'no listener'));
      assert(completed===0&&job.video===video&&job.onSeeked===callback,'listenSeekCallback must not invoke or replace callback/video');
    ''',
    'video_seek_register': r'''
      let job,calls=0,registered=[];
      function completeSeekJob(value){assert(value===job,'seeked callback must complete its original job');calls++;}
      const video={addEventListener(name,fn){registered.push([name,fn]);}};
      job={video,onSeeked:null};registerSeekEvent(job);
      assert(calls===0,'registerSeekEvent must defer completion until the seeked event');
      assert(typeof job.onSeeked==='function','registerSeekEvent must store a function in job.onSeeked');
      assert(registered.length===1&&registered[0][0]==='seeked'&&registered[0][1]===job.onSeeked,'registerSeekEvent must register the original stored callback once');
      if(typeof job.onSeeked==='function')job.onSeeked();
      assert(calls===1&&job.video===video,'seeked callback must call completeSeekJob exactly once without replacing video');
    ''',
    'video_seek_timer': r'''
      let job,callback,delay,calls=0,handle;
      function setTimeout(fn,ms){callback=fn;delay=ms;return handle;}const window={setTimeout};
      function failSeekJob(value,error){assert(value===job&&error instanceof Error&&error.message,'seek timeout must fail original job with an Error');calls++;}
      for(handle of [0,37,311]){
        job={timer:null};callback=null;delay=0;calls=0;scheduleSeekTimeout(job);
        assert(job.timer===handle,'job.timer expected actual setTimeout return handle '+handle+'; actual='+String(job.timer));
        assert(delay===5000&&typeof callback==='function','scheduleSeekTimeout must schedule a function after 5000 milliseconds');
        assert(calls===0,'scheduleSeekTimeout must not reject before timeout fires');
        if(typeof callback==='function')callback();
        assert(calls===1,'seek timeout must call failSeekJob once');
      }
    ''',
    'video_seek_assign': r'''
      let job,writes=[],failed=[],shouldThrow=false;const actualError=new Error('Actual assignment denied');
      function failSeekJob(value,error){failed.push([value,error]);}
      const video={set currentTime(value){if(shouldThrow)throw actualError;writes.push(value);}};
      for(const target of [0,2.75]){
        writes=[];failed=[];job={video};let thrown=null;
        try{assignSeekTarget(job,target);}catch(error){thrown=error;}
        assert(thrown===null,'assignSeekTarget('+target+') must accept already validated seconds including zero without throwing; observed '+String(thrown));
        assert(writes.length===1&&writes[0]===target,'assignSeekTarget('+target+') must assign supplied currentTime exactly once; observed writes='+JSON.stringify(writes));
        assert(failed.length===0,'valid seek assignment must not reject or call unrelated event callbacks; observed failure count='+failed.length);
        assert(job.video===video,'assignSeekTarget must retain original video object');
      }
      shouldThrow=true;job={video};failed=[];let uncaught=null;
      try{assignSeekTarget(job,4);}catch(error){uncaught=error;}
      assert(uncaught===null,'assignSeekTarget must catch a video assignment exception and delegate actual Error to failSeekJob; observed uncaught '+String(uncaught));
      assert(failed.length===1&&failed[0][0]===job&&failed[0][1]===actualError,'assignSeekTarget must delegate original caught Error with original job');
    ''',
    'video_seek_job': r'''
      for(const video of [{currentTime:0},{currentTime:3}]){
        const resolve=()=>{},reject=()=>{},job=makeSeekJob(video,resolve,reject);
        assert(job&&job.video===video&&job.resolve===resolve&&job.reject===reject,'makeSeekJob must retain supplied video and both callback identities');
        assert(job.timer===null&&job.onSeeked===null,'makeSeekJob returned object must have timer=null and onSeeked=null properties; actual keys='+JSON.stringify(Object.keys(job))+' timer='+String(job.timer)+' onSeeked='+String(job.onSeeked));
      }
    ''',
    'video_seek_clear': r'''
      let cleared=[],removed=[];function clearTimeout(id){cleared.push(id);}
      const window={clearTimeout};
      for(const timer of [0,32,null]){
        const handler=()=>{},resolve=()=>{},reject=()=>{},video={removeEventListener(name,fn){removed.push([name,fn]);}};
        const job={video,resolve,reject,timer,onSeeked:handler};cleared=[];removed=[];clearSeekJob(job);
        assert((timer===null?cleared.length===0:cleared.length===1&&cleared[0]===timer),'clearSeekJob must clear its timer, including handle zero');
        assert(removed.length===1&&removed[0][0]==='seeked'&&removed[0][1]===handler,'clearSeekJob must remove the original named seeked handler');
        assert(job.timer===null&&job.onSeeked===null&&job.video===video&&job.resolve===resolve&&job.reject===reject,'clearSeekJob must clear only its handles and retain supplied objects/callbacks');
      }
      const job={timer:null,onSeeked:null,video:{removeEventListener(){throw new Error('No listener to remove');}}};clearSeekJob(job);
    ''',
    'video_seek_complete': r'''
      let log=[],job;function clearSeekJob(value){assert(value===job,'completion must clean the same seek job');log.push('clear');}
      job={resolve(){log.push('resolve');},reject(){log.push('reject');}};
      completeSeekJob(job);assert(JSON.stringify(log)==='["clear","resolve"]','completeSeekJob must clear handles before resolving, never reject');
    ''',
    'video_seek_fail': r'''
      let log=[],job;const error=new Error('Actual seek failure');
      function clearSeekJob(value){assert(value===job,'failure must clean the same seek job');log.push('clear');}
      job={resolve(){log.push('resolve');},reject(value){assert(value===error,'failSeekJob must reject the actual supplied Error');log.push('reject');}};
      failSeekJob(job,error);assert(JSON.stringify(log)==='["clear","reject"]','failSeekJob must clear handles before rejecting, never resolve');
    ''',
    'video_seek_arm': r'''
      let events=[],timerCallback=null,timerMs=0,assignmentFailure=false,current=0,job,returnedHandle=0;
      function setTimeout(fn,ms){timerCallback=fn;timerMs=ms;events.push('timer');return returnedHandle;}
      const window={setTimeout};
      const video={addEventListener(name,fn){assert(name==='seeked'&&fn===job.onSeeked,'armSeekJob must register its stored seeked handler');events.push('listen');},
        set currentTime(value){events.push('assign');if(assignmentFailure)throw new Error('Assignment blocked');current=value;},get currentTime(){return current;}};
      function completeSeekJob(value){assert(value===job,'seeked callback must complete its original job');events.push('complete');}
      function failSeekJob(value,error){assert(value===job&&error instanceof Error,'failure callback must receive original job and actual Error');events.push('fail:'+error.message);}
      for(const [target,handle] of [[0,0],[2.75,37],[4,311]]){
        returnedHandle=handle;timerCallback=null;timerMs=0;
        events=[];job={video,timer:null,onSeeked:null};armSeekJob(job,target);
        assert(JSON.stringify(events)==='["listen","timer","assign"]'&&current===target,'armSeekJob must register event and timeout before assigning requested time, including zero');
        assert(job.timer===returnedHandle,'job.timer expected the handle returned immediately by browser setTimeout: '+returnedHandle+'; actual='+String(job.timer));
        assert(timerMs===5000,'setTimeout delay expected 5000 milliseconds; actual='+timerMs);
        assert(typeof job.onSeeked==='function','armSeekJob must assign an actual seeked callback to job.onSeeked');
        if(typeof job.onSeeked==='function'){job.onSeeked();assert(events.at(-1)==='complete','seeked callback must delegate to completeSeekJob');}
        assert(typeof timerCallback==='function','armSeekJob must immediately call browser setTimeout, before any seeked event');
        if(typeof timerCallback==='function'){timerCallback();assert(events.at(-1).startsWith('fail:'),'timeout callback must delegate an Error to failSeekJob');}
      }
      assignmentFailure=true;events=[];job={video,timer:null,onSeeked:null};armSeekJob(job,4);
      assert(events.at(-1)==='fail:Assignment blocked','assignment exception must delegate actual error to failSeekJob');
    ''',
    'video_export_mime': r'''
      let supported=new Set(),probes=[];
      const MediaRecorder={isTypeSupported(...args){assert(args.length===1,'MediaRecorder.isTypeSupported must receive one complete MIME string');const value=args[0];probes.push(value);return supported.has(value);}};
      for(const [values,expected] of [
        [['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'],'video/webm;codecs=vp9,opus'],
        [['video/webm;codecs=vp8,opus','video/webm'],'video/webm;codecs=vp8,opus'],
        [['video/webm'],'video/webm']]){
        supported=new Set(values);probes=[];
        const actual=chooseWebMMime();
        assert(actual===expected,'chooseWebMMime expected first supported literal '+JSON.stringify(expected)+' for available types '+JSON.stringify(values)+'; actual='+JSON.stringify(actual));
        assert(probes.every(value=>['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'].includes(value)),'chooseWebMMime must probe actual WebM MIME types');
      }
      supported.clear();let rejected=false,returned;try{returned=chooseWebMMime();}catch(error){rejected=!!error.message;}
      assert(rejected,'chooseWebMMime expected throw Error after every support probe returned false; actual='+JSON.stringify(returned));
    ''',
    'video_export_seek': r'''
      const timers=new Map(),listeners=new Map();let nextTimer=1,time=0,assignError=false,writes=[];
      function setTimeout(fn,ms){const id=nextTimer++;timers.set(id,{fn,ms});return id;}
      function clearTimeout(id){timers.delete(id);}
      const window={setTimeout,clearTimeout};
      ui.preview={get currentTime(){return time;},set currentTime(value){if(assignError)throw new Error('Cannot seek this clip');writes.push({value,armed:listeners.has('seeked')});time=value;},
        addEventListener(name,fn,options){listeners.set(name,{fn,once:!!options?.once});},
        removeEventListener(name,fn){if(listeners.get(name)?.fn===fn)listeners.delete(name);}};
      function fireSeek(){const entry=listeners.get('seeked');if(entry?.once)listeners.delete('seeked');entry?.fn();}
      app.start=2;time=2.01;await seekExportStart();
      assert(writes.length===0&&timers.size===0&&listeners.size===0,'near trim start must resolve immediately without seeking or timers');
      for(const initial of [0,2.05,8]){
        time=initial;writes=[];const pending=seekExportStart();
        assert(writes.length===1&&writes[0].value===2&&writes[0].armed,'seekExportStart must attach seeked before assigning trim start');
        assert([...timers.values()].some(t=>t.ms===5000),'seekExportStart must bound waiting to five seconds');
        fireSeek();await pending;
        assert(timers.size===0&&listeners.size===0,'successful seek must remove its listener and timeout');
      }
      time=0;const pending=seekExportStart();let failure='';
      const timeout=[...timers.values()][0];if(timeout)timeout.fn();
      try{await pending;}catch(error){failure=error.message;}
      assert(failure.length>0&&timers.size===0&&listeners.size===0,'seek timeout must reject and clean up');
      time=0;assignError=true;failure='';try{await seekExportStart();}catch(error){failure=error.message;}
      assert(failure.includes('Cannot seek this clip')&&timers.size===0&&listeners.size===0,'seek assignment failure must reject with actual error and clean up');
    ''',
    'video_export_audio': r'''
      let sources=0,destinations=0,resumes=0,connections=[],resumeError=false;
      const audioTrack={kind:'audio'},speaker={speaker:true},destination={stream:{getAudioTracks(){return [audioTrack];}}};
      class AudioContext{
        constructor(){this.destination=speaker;}
        createMediaElementSource(element){assert(element===ui.preview,'audio source must use existing preview');sources++;return {connect(target){connections.push(target);}};}
        createMediaStreamDestination(){destinations++;return destination;}
        resume(){resumes++;return resumeError?Promise.reject(new Error('Audio permission denied')):Promise.resolve();}
      }
      const window={AudioContext};ui.preview={};ui.status.textContent='';
      function setStatus(message){ui.status.textContent=String(message);}
      app.audioContext=null;app.audioSource=null;app.audioDest=null;
      for(let index=0;index<2;index++){
        const tracks=[],stream={getAudioTracks(){return tracks;},addTrack(track){tracks.push(track);}};
        assert(await attachExportAudio(stream)===true,'working audio must return Boolean true');
        assert(tracks.length===1&&tracks[0]===audioTrack,'audio destination track must be added once to each export stream');
      }
      assert(sources===1&&destinations===1&&connections.length===2&&connections.includes(speaker)&&connections.includes(destination),'audio source and destination must be reused without duplicate connections');
      assert(resumes===2,'audio context must be resumed for each export');
      resumeError=true;const tracks=[];
      assert(await attachExportAudio({getAudioTracks(){return tracks;},addTrack(t){tracks.push(t);}})===false,'audio resume rejection must return Boolean false instead of rejecting export');
      assert(tracks.length===0&&/silent/i.test(ui.status.textContent),'audio failure must report explicit silent export and add no audio tracks');
      window.AudioContext=undefined;app.audioContext=null;app.audioSource=null;app.audioDest=null;ui.status.textContent='';
      assert(await attachExportAudio({addTrack(){throw new Error('No audio available');}})===false&&/silent/i.test(ui.status.textContent),'missing AudioContext must return false with silent-export status');
    ''',
    'video_export_cleanup': r'''
      let pauses=0,cancelled=[],busy=[];
      function cancelAnimationFrame(id){cancelled.push(id);}
      function setBusy(value){busy.push(value);app.busy=value;}
      ui.preview={pause(){pauses++;}};ui.progressLabel={textContent:'52%'};
      for(const raf of [0,27,null]){
        let videoStops=0,audioStops=0;const video={kind:'video',stop(){videoStops++;}},audio={kind:'audio',stop(){audioStops++;}};
        const stream={getVideoTracks(){return [video];},getTracks(){return [video,audio];}};
        app.raf=raf;app.busy=true;ui.playBtn.textContent='Pause';ui.progressLabel.textContent='52%';cancelled=[];
        cleanupExport(stream);
        assert(videoStops===1&&audioStops===0,'cleanupExport must stop only canvas video tracks; audio destination is reusable');
        assert((raf===null?cancelled.length===0:cancelled.length===1&&cancelled[0]===raf)&&app.raf===null,'cleanupExport must cancel and clear its RAF handle, including handle zero');
        assert(ui.playBtn.textContent==='Play'&&ui.progressLabel.textContent===''&&app.busy===false,'cleanupExport must reset playback label, progress and busy state');
      }
      cleanupExport(null);assert(pauses===4&&busy.every(value=>value===false),'cleanupExport must handle an absent stream and pause/reset every time');
    ''',
    'video_export_finish': r'''
      let cleaned=0,statuses=[],created=[],revoked=[];
      function cleanupExport(){cleaned++;app.busy=false;}
      function setStatus(message,error){statuses.push([String(message),error]);}
      class Blob{constructor(parts,options){this.parts=parts;this.type=options.type;this.size=parts.reduce((sum,part)=>sum+part.size,0);}}
      const URL={createObjectURL(blob){created.push(blob);return 'blob:new-export';},revokeObjectURL(url){revoked.push(url);}};
      ui.downloadLink={href:'',download:'',hidden:true};app.recorder={mimeType:'video/webm;codecs=vp8,opus'};
      for(const audio of [false,true]){
        app.cancelled=false;app.chunks=[{size:42},{size:58}];app.downloadURL='blob:old-export';statuses=[];created=[];revoked=[];
        const parts=app.chunks;finishExport(null,audio,'');
        assert(created.length===1&&created[0].parts===parts&&created[0].size===100&&created[0].type===app.recorder.mimeType,'finishExport must create a real Blob from actual recorded chunks with recorder MIME');
        assert(revoked.length===1&&revoked[0]==='blob:old-export'&&app.downloadURL==='blob:new-export','finishExport must revoke previous download URL before storing new one');
        assert(ui.downloadLink.href===app.downloadURL&&ui.downloadLink.download==='clip-mini.webm'&&ui.downloadLink.hidden===false,'finishExport must expose the newly recorded WebM download');
        assert(statuses.some(([message,error])=>message.includes('100')&&new RegExp(audio?'audio':'silent','i').test(message)&&error!==true),'export ready status must include real byte count and audio/silent information');
      }
      for(const [cancelled,error,size] of [[true,'',100],[false,'Encoder permission denied',100],[false,'',0]]){
        app.cancelled=cancelled;app.chunks=[{size}];created=[];statuses=[];ui.downloadLink.hidden=true;
        finishExport(null,true,error);
        assert(created.length===0&&ui.downloadLink.hidden===true,'cancelled/error/empty export must not expose a new download');
        assert(app.chunks.length===0,'cancelled/error/empty export must discard partial chunks');
        assert(statuses.some(([message,flag])=>error?message.includes(error)&&flag===true:cancelled?/cancel/i.test(message):flag===true),'finishExport must report actual error, cancellation or empty recording');
      }
      assert(cleaned===5,'finishExport must always invoke cleanupExport');
    ''',
    'video_export_recorder': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      class MediaRecorder{constructor(stream,options){this.stream=stream;this.mimeType=options.mimeType;this.state='recording';this.stops=0;}stop(){this.stops++;this.state='inactive';this.onstop();}}
      const stream={};app.chunks=[];
      const recorder=createExportRecorder(stream,'video/webm',true);
      assert(recorder===app.recorder&&recorder.stream===stream&&recorder.mimeType==='video/webm','createExportRecorder must store and return the real configured recorder');
      recorder.ondataavailable({data:{size:0}});const chunk={size:20};recorder.ondataavailable({data:chunk});
      assert(app.chunks.length===1&&app.chunks[0]===chunk,'recorder must retain nonempty chunks without replacing them');
      recorder.onstop();assert(finished.length===1&&finished[0][0]===stream&&finished[0][1]===true&&!finished[0][2],'recorder stop must call finishExport with stream and actual audio flag');
      finished=[];recorder.onerror({error:new Error('Encoder exploded')});
      assert(recorder.stops===1&&finished.length===1&&finished[0][2]==='Encoder exploded','recorder error must stop recording and preserve actual error for finalization');
    ''',
    'video_export_frames': r'''
      let paints=0,queued=[],stops=0;
      function paintFrame(){paints++;}
      function requestAnimationFrame(fn){queued.push(fn);return queued.length+10;}
      ui.progressLabel={textContent:''};ui.preview={currentTime:2,ended:false};
      app.start=2;app.end=6;app.cancelled=false;app.recorder={state:'recording',stop(){stops++;this.state='inactive';}};
      watchExportFrames();assert(paints===1&&queued.length===1&&app.raf!==null,'watchExportFrames must paint and schedule the active recording');
      ui.preview.currentTime=4;queued.shift()();assert(paints===2&&/50/.test(ui.progressLabel.textContent),'frame progress must reflect selected trim interval, not full duration');
      ui.preview.currentTime=5.98;queued.shift()();assert(stops===1&&app.recorder.state==='inactive'&&ui.preview.currentTime===6&&queued.length===0,'frame loop must stop at selected trim end and stop scheduling');
      for(const [cancelled,ended] of [[true,false],[false,true]]){
        app.recorder.state='recording';app.cancelled=cancelled;ui.preview.ended=ended;ui.preview.currentTime=3;queued=[];const before=stops;
        watchExportFrames();assert(stops===before+1&&queued.length===0,'cancelled or ended video must stop recording without scheduling another frame');
      }
    ''',
    'video_export_orchestration': r'''
      let log=[],valid=true,playError=false,stream={getVideoTracks(){return [];}};
      function validateTrim(){log.push('validate');return valid;}
      function chooseWebMMime(){log.push('mime');return 'video/webm';}
      function setBusy(value){log.push('busy:'+value);app.busy=value;}
      function prepareCanvas(){log.push('canvas');app.canvas={captureStream(fps){assert(fps===24,'capture stream must use 24 fps');log.push('capture');return stream;}};}
      async function seekExportStart(){log.push('seek');}
      function paintFrame(){log.push('paint');}
      async function attachExportAudio(value){assert(value===stream,'audio must attach to captured stream');log.push('audio');return true;}
      function createExportRecorder(value,mime,audio){assert(value===stream&&mime==='video/webm'&&audio===true,'export must pass capture stream, selected MIME and actual audio flag');log.push('recorder');return app.recorder={state:'inactive',onstop(){},start(){log.push('start');this.state='recording';},stop(){log.push('stop');this.state='inactive';if(this.onstop)this.onstop();}};}
      function watchExportFrames(){log.push('frames');}
      function finishExport(value,audio,error){log.push('finish:'+error);app.busy=false;}
      function setStatus(message,error){log.push('status:'+message);}
      class MediaRecorder{};class HTMLCanvasElement{};HTMLCanvasElement.prototype.captureStream=function(){};
      ui.preview={play(){log.push('play');return playError?Promise.reject(new Error('Playback refused')):Promise.resolve();}};
      ui.downloadLink={hidden:false};app.canvas={captureStream(){}};
      for(const [loaded,busy] of [[false,false],[false,true],[true,true]]){
        app.loaded=loaded;app.busy=busy;log=[];await exportVideo();assert(log.length===0,'exportVideo must do nothing when unloaded or busy');
      }
      app.loaded=true;app.busy=false;valid=false;log=[];await exportVideo();assert(JSON.stringify(log)==='["validate"]','invalid trim must not begin export');
      valid=true;app.busy=false;app.cancelled=true;app.chunks=[{size:9}];log=[];await exportVideo();
      assert(app.cancelled===false&&app.chunks.length===0&&ui.downloadLink.hidden===true,'new export must reset cancellation/chunks and hide old download');
      const order=['mime','busy:true','canvas','seek','paint','capture','audio','recorder','start','play','frames'];
      assert(order.every((name,index)=>log.includes(name)&&(index===0||log.indexOf(name)>log.indexOf(order[index-1]))),'export must prepare/seek/paint/capture/audio/record/start before playback and frame loop; actual='+JSON.stringify(log));
      app.busy=false;playError=true;log=[];await exportVideo();
      assert(log.includes('stop')&&log.some(value=>value==='finish:Playback refused')&&app.busy===false,'play rejection must stop recorder and finalize with actual error');
      assert(!log.includes('frames'),'failed play must not start frame loop');
    ''',
}

ASYNC_EXPORT_CHECKS = {'video_export_seek', 'video_export_audio', 'video_export_orchestration'}

# The parameter-only worker and app-level caller face the same seek lifecycle
# cases. No behavior is removed when the model writes these as separate parts.
EXPORT_CASES['video_export_wait']=EXPORT_CASES['video_export_seek'].replace(
    'await seekExportStart()', 'await waitForVideoTime(ui.preview,app.start)').replace(
    'const pending=seekExportStart()', 'const pending=waitForVideoTime(ui.preview,app.start)')
ASYNC_EXPORT_CHECKS.add('video_export_wait')

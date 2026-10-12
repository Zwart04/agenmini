"""Recorder API fixtures; evaluator-only, never supplied as application source."""

EXPORT_CASES = {
    'video_audio_silent_status': r'''
      let statuses=[];function setStatus(message){statuses.push(String(message));}
      for(const message of ['Audio permission denied','Different audio problem']){
        statuses=[];const result=reportSilentAudio(new Error(message));
        assert(result===false,'silent audio reporter must return Boolean false; observed '+String(result));
        assert(statuses.length===1&&statuses[0].startsWith('Silent export')&&statuses[0].includes(message),'silent audio reporter must send one explicit Silent export status with actual Error message; observed '+JSON.stringify(statuses));
      }
    ''',
    'video_audio_require_tracks': r'''
      let calls=[],available=true;const stream={},destination={};
      function addExportAudioTracks(value,target){calls.push([value,target]);return available;}
      assert(requireExportAudioTracks(stream,destination)===true,'audio track requirement must return Boolean true after actual attachment succeeds');
      assert(calls.length===1&&calls[0][0]===stream&&calls[0][1]===destination,'audio track requirement must use original stream and destination once');
      calls=[];available=false;let failure='';
      try{requireExportAudioTracks(stream,destination);}catch(error){failure=error.message;}
      assert(calls.length===1&&calls[0][0]===stream&&calls[0][1]===destination&&failure.length>0,'audio track requirement must throw a descriptive Error when actual attachment returns false');
    ''',
    'video_audio_track_membership': r'''
      const track={kind:'audio'},other={kind:'audio'};let tracks=[],calls=0;
      const stream={getAudioTracks(){calls++;return tracks;}};
      for(const initial of [[],[other],[track],[other,track]]){
        tracks=[...initial];calls=0;const result=hasExportAudioTrack(stream,track);
        assert(result===initial.includes(track),'track membership must return Boolean for original object identity; expected='+initial.includes(track)+' observed='+String(result));
        assert(calls===1&&tracks.length===initial.length&&tracks.every((value,index)=>value===initial[index]),'track membership must read once without mutating original stream tracks');
      }
    ''',
    'video_audio_single_track': r'''
      const track={kind:'audio'},other={kind:'audio'};let tracks=[],added=[];
      const stream={getAudioTracks(){return tracks;},addTrack(value){added.push(value);tracks.push(value);}};
      for(const initial of [[],[other],[track]]){
        tracks=[...initial];added=[];addSingleExportAudioTrack(stream,track);
        const expected=initial.includes(track)?0:1;
        const scenario=initial.includes(track)?'supplied track already present: do not add it again':initial.length?'existing unrelated track: add supplied track once':'no existing tracks: add supplied track once';
        assert(added.length===expected,scenario+'; expected additions='+expected+' observed='+added.length);
        if(expected===1&&added.length===1)assert(added[0]===track,'stream.addTrack must receive original supplied track object; observed same identity='+(added[0]===track));
        assert(initial.every(value=>tracks.includes(value))&&tracks.includes(track),'single track attachment must preserve existing tracks and retain original supplied track');
      }
    ''',
    'video_audio_source': r'''
      let calls=0;const video={},source={connect(){}};
      const context={createMediaElementSource(element){calls++;assert(element===video,'audio source factory must pass original video');return source;}};
      assert(createExportAudioSource(context,video)===source&&calls===1,'audio source factory must return actual browser source from one method call');
    ''',
    'video_audio_destination': r'''
      let calls=0;const destination={stream:{}};
      const context={createMediaStreamDestination(){calls++;return destination;}};
      assert(createExportAudioDestination(context)===destination&&calls===1,'audio destination factory must return actual destination from one method call');
    ''',
    'video_audio_targets': r'''
      const speaker={},destination={},context={destination:speaker},targets=[];
      const source={connect(target){targets.push(target);}};
      connectExportAudioTargets(source,context,destination);
      assert(targets.length===2&&targets[0]===speaker&&targets[1]===destination,'connect audio source to original playback and recording targets once each');
    ''',
    'video_audio_context': r'''
      let creations=0;class AudioContext{constructor(){creations++;}}
      const window={AudioContext};app.audioContext=null;
      let first,second,failure='';
      try{first=getExportAudioContext();second=getExportAudioContext();}catch(error){failure=error.message;}
      assert(!failure,'getExportAudioContext must accept available window.AudioContext constructor; observed '+failure);
      if(!failure)assert(first instanceof AudioContext&&first===second&&first===app.audioContext&&creations===1,'audio context must store actual instance in app.audioContext and reuse it; observed creations='+creations+' stored='+(first===app.audioContext)+' reused='+(first===second));
      window.AudioContext=undefined;window.webkitAudioContext=AudioContext;app.audioContext=null;creations=0;failure='';let fallback;
      try{fallback=getExportAudioContext();}catch(error){failure=error.message;}
      assert(!failure,'getExportAudioContext must accept available window.webkitAudioContext when primary constructor is absent; observed '+failure);
      if(!failure)assert(fallback instanceof AudioContext&&fallback===app.audioContext&&creations===1,'webkit audio context must instantiate once and store actual instance; observed creations='+creations+' stored='+(fallback===app.audioContext));
      window.webkitAudioContext=undefined;app.audioContext=null;failure='';
      try{getExportAudioContext();}catch(error){failure=error.message;}
      assert(failure.length>0&&app.audioContext===null,'missing audio constructor must throw a descriptive Error without storing fake state');
    ''',
    'video_audio_connections': r'''
      let sources=0,destinations=0,connections=[];const video={},speaker={},destination={stream:{}},source={connect(target){connections.push(target);}};
      const context={destination:speaker,createMediaElementSource(element){assert(element===video,'audio source must use supplied video argument');sources++;return source;},createMediaStreamDestination(){destinations++;return destination;}};
      app.audioSource=null;app.audioDest=null;
      const first=connectExportAudio(context,video),second=connectExportAudio(context,video);
      assert(first===destination&&second===destination&&app.audioSource===source&&app.audioDest===destination,'audio connections must retain and return actual browser objects');
      assert(sources===1&&destinations===1&&connections.length===2&&connections.includes(speaker)&&connections.includes(destination),'audio connections must initialize once and connect both playback and recording destinations');
    ''',
    'video_audio_tracks': r'''
      const first={kind:'audio'},second={kind:'audio'};let tracks=[],added=[];
      const stream={getAudioTracks(){return tracks;},addTrack(track){added.push(track);tracks.push(track);}};
      let available=[first,second];const destination={stream:{getAudioTracks(){return available;}}};
      const result=addExportAudioTracks(stream,destination);
      assert(result===true,'audio destination with two tracks must return Boolean true; observed '+String(result));
      assert(added.length===2&&added[0]===first&&added[1]===second,'audio destination must attach both original tracks using stream.addTrack; expected additions=2 observed='+added.length);
      tracks=[first,second];added=[];
      assert(addExportAudioTracks(stream,destination)===true&&added.length===0&&tracks.length===2,'audio tracks already attached must not be duplicated; expected new additions=0 observed='+added.length);
      available=[];tracks=[];added=[];
      assert(addExportAudioTracks(stream,destination)===false&&added.length===0,'an empty audio destination must return Boolean false without adding fake tracks');
    ''',
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
      const audioTrack={kind:'audio'},speaker={speaker:true};let availableTracks=[audioTrack];
      const destination={stream:{getAudioTracks(){return availableTracks;}}};
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
      availableTracks=[];ui.status.textContent='';const emptyTracks=[];let emptyResult,rejected='';
      try{emptyResult=await attachExportAudio({getAudioTracks(){return emptyTracks;},addTrack(value){emptyTracks.push(value);}});}catch(error){rejected=error.message;}
      assert(!rejected,'empty audio destination must return false without rejecting export; observed '+rejected);
      assert(emptyResult===false&&emptyTracks.length===0,'empty audio destination must return Boolean false without fake tracks; observed result='+String(emptyResult)+' additions='+emptyTracks.length);
      assert(/silent/i.test(ui.status.textContent),'empty audio destination must report explicit silent export; observed status='+ui.status.textContent);
      availableTracks=[audioTrack];ui.status.textContent='';
      resumeError=true;const tracks=[];
      let result;rejected='';
      try{result=await attachExportAudio({getAudioTracks(){return tracks;},addTrack(t){tracks.push(t);}});}catch(error){rejected=error.message;}
      assert(!rejected,'recoverable audio resume failure must return false without rejecting export; observed '+rejected);
      assert(result===false,'audio resume failure must return Boolean false; observed '+String(result));
      assert(tracks.length===0,'audio resume failure must not add tracks; observed additions='+tracks.length);
      assert(/silent/i.test(ui.status.textContent)&&ui.status.textContent.includes('Audio permission denied'),'audio resume failure must report silent export and actual browser Error message; observed status='+ui.status.textContent);
      window.AudioContext=undefined;app.audioContext=null;app.audioSource=null;app.audioDest=null;ui.status.textContent='';
      result=undefined;rejected='';
      try{result=await attachExportAudio({addTrack(){throw new Error('No audio available');}});}catch(error){rejected=error.message;}
      assert(!rejected&&result===false,'missing AudioContext must return false without rejecting; observed result='+String(result)+' error='+rejected);
      assert(/silent/i.test(ui.status.textContent),'missing AudioContext must report silent export; observed status='+ui.status.textContent);
    ''',
    'video_stop_export_tracks': r'''
      let videoStops=0,audioStops=0;
      const video={stop(){videoStops++;}},audio={stop(){audioStops++;}};
      const stream={getVideoTracks(){return [video];},getTracks(){return [video,audio];}};
      stopExportVideoTracks(stream);
      assert(videoStops===1&&audioStops===0,'stopExportVideoTracks must stop actual video tracks once and preserve audio tracks');
      stopExportVideoTracks(null);
      assert(videoStops===1&&audioStops===0,'absent stream must not stop additional tracks');
    ''',
    'video_cancel_export_frame': r'''
      let cancelled=[];function cancelAnimationFrame(handle){cancelled.push(handle);}
      const window={cancelAnimationFrame};
      for(const handle of [0,27,311,null]){
        cancelled=[];cancelExportFrame(handle);
        assert(handle===null?cancelled.length===0:cancelled.length===1&&cancelled[0]===handle,'cancelExportFrame must call native cancelAnimationFrame once with actual numeric handle including zero; handle='+handle+' observed='+JSON.stringify(cancelled));
      }
    ''',
    'video_export_cleanup': r'''
      let pauses=0,cancelled=[],busy=[];
      function cancelAnimationFrame(id){cancelled.push(id);}
      const window={cancelAnimationFrame};
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
    'video_export_discard': r'''
      let statuses=[];function setStatus(...args){statuses.push(args);}
      ui.downloadLink={hidden:false};
      for(const [message,error] of [['Encoder permission denied',true],['Cancelled',false],['Empty recording',true]]){
        app.chunks=[{size:100}];ui.downloadLink.hidden=false;statuses=[];
        discardExportResult(message,error);
        assert(app.chunks.length===0&&ui.downloadLink.hidden===true,'discard must clear partial chunks and hide the download');
        assert(statuses.length===1&&statuses[0][0]===message&&statuses[0][1]===error,'discard must report supplied message and error flag unchanged');
      }
    ''',
    'video_recorded_blob': r'''
      class Blob{constructor(parts,options){this.parts=parts;this.type=options.type;}}
      const window={Blob};globalThis.Blob=Blob;
      for(const mime of ['video/webm;codecs=vp8,opus','video/webm']){
        app.chunks=[{size:42},{size:58}];app.recorder={mimeType:mime};
        const parts=app.chunks;const blob=createRecordedBlob();
        assert(blob instanceof Blob,'createRecordedBlob must return an actual Blob instance');
        assert(Array.isArray(blob.parts)&&blob.parts.length===parts.length&&blob.parts.every((part,index)=>part===parts[index]),'Blob parts must be a flat ordered list of the original recorded chunks; expected count='+parts.length+' observed count='+blob.parts?.length+' first item is nested array='+Array.isArray(blob.parts?.[0]));
        assert(blob.type===mime,'Blob MIME must match actual recorder; expected='+mime+' observed='+String(blob.type));
        assert(app.chunks===parts,'createRecordedBlob must preserve original chunk array');
      }
    ''',
    'video_recording_url': r'''
      let created=[],revoked=[];
      const URL={createObjectURL(blob){created.push(blob);return 'blob:new';},revokeObjectURL(value){revoked.push(value);}};
      const window={URL};globalThis.URL=URL;
      const blob={size:217};
      for(const previous of [null,'blob:previous']){
        created=[];revoked=[];const value=replaceRecordingURL(blob,previous);
        assert(value==='blob:new'&&created.length===1&&created[0]===blob,'URL helper must return new object URL from original recorded Blob');
        assert(previous?revoked.length===1&&revoked[0]===previous:revoked.length===0,'URL helper must revoke original previous string once, only when present');
      }
    ''',
    'video_recording_link': r'''
      const link={href:'blob:old',hidden:true,download:'old.webm'};
      exposeRecordingLink(link,'blob:current');
      assert(link.href==='blob:current'&&link.download==='clip-mini.webm'&&link.hidden===false,'link helper must update href, download filename and hidden on original supplied anchor');
    ''',
    'video_recording_status': r'''
      let statuses=[];function setStatus(...args){statuses.push(args);}
      for(const [size,audio] of [[100,true],[217,false],[314,true]]){
        statuses=[];reportRecordingReady(size,audio);
        assert(statuses.length===1&&String(statuses[0][0]).includes(String(size))&&new RegExp(audio?'audio':'silent','i').test(statuses[0][0])&&statuses[0][1]!==true,'recording status must report actual byte count and audio/silent success once; observed='+JSON.stringify(statuses));
      }
    ''',
    'video_publish_recording': r'''
      let created=[],revoked=[],statuses=[];
      const URL={createObjectURL(blob){created.push(blob);return 'blob:new-recording';},revokeObjectURL(url){revoked.push(url);}};
      const window={URL};globalThis.URL=URL;
      function setStatus(...args){statuses.push(args);}
      const anchor={};ui.downloadLink=anchor;
      for(const [audio,old,size] of [[true,'blob:old',100],[false,null,217]]){
        created=[];revoked=[];statuses=[];app.downloadURL=old;const blob={size};
        publishRecordedBlob(blob,audio);
        assert(ui.downloadLink===anchor,'publish must update the original on-page anchor, not replace its object');
        assert(created.length===1&&created[0]===blob,'publish must create an object URL from supplied recorded Blob once');
        assert(old?revoked.length===1&&revoked[0]===old:revoked.length===0,'publish must revoke only the previous download URL when present');
        assert(app.downloadURL==='blob:new-recording'&&ui.downloadLink.href===app.downloadURL&&ui.downloadLink.download==='clip-mini.webm'&&ui.downloadLink.hidden===false,'publish must expose new recorded WebM URL');
        assert(statuses.length===1&&String(statuses[0][0]).includes(String(size))&&new RegExp(audio?'audio':'silent','i').test(statuses[0][0])&&statuses[0][1]!==true,'publish must report actual size and audio/silent mode once');
      }
    ''',
    'video_export_finish': r'''
      let cleaned=0,statuses=[],created=[],revoked=[],expectedStream=null;
      function cleanupExport(stream){assert(stream===expectedStream,'finishExport must forward original stream to cleanup, including null');cleaned++;app.busy=false;}
      function setStatus(message,error){statuses.push([String(message),error]);}
      class Blob{constructor(parts,options){this.parts=parts;this.type=options.type;this.size=parts.reduce((sum,part)=>sum+part.size,0);}}
      const URL={createObjectURL(blob){created.push(blob);return 'blob:new-export';},revokeObjectURL(url){revoked.push(url);}};
      const window={Blob,URL};globalThis.Blob=Blob;globalThis.URL=URL;
      ui.downloadLink={href:'',download:'',hidden:true};app.recorder={mimeType:'video/webm;codecs=vp8,opus'};
      for(const audio of [false,true]){
        app.cancelled=false;app.chunks=[{size:42},{size:58}];app.downloadURL='blob:old-export';statuses=[];created=[];revoked=[];
        const parts=app.chunks,anchor=ui.downloadLink;expectedStream=audio?{}:null;const before=cleaned;finishExport(expectedStream,audio,'');
        assert(cleaned===before+1,'finishExport must clean up once, including when stream is null; expected='+String(before+1)+' observed='+cleaned);
        assert(ui.downloadLink===anchor,'finishExport must update the original on-page download anchor');
        assert(created.length===1&&created[0].parts.length===parts.length&&created[0].parts.every((part,index)=>part===parts[index])&&created[0].size===100&&created[0].type===app.recorder.mimeType,'finishExport must create a real Blob from flat original recorded chunks with recorder MIME');
        assert(revoked.length===1&&revoked[0]==='blob:old-export'&&app.downloadURL==='blob:new-export','finishExport must revoke previous download URL before storing new one');
        assert(ui.downloadLink.href===app.downloadURL&&ui.downloadLink.download==='clip-mini.webm'&&ui.downloadLink.hidden===false,'finishExport must expose the newly recorded WebM download');
        assert(statuses.some(([message,error])=>message.includes('100')&&new RegExp(audio?'audio':'silent','i').test(message)&&error!==true),'export ready status must include real byte count and audio/silent information');
      }
      for(const [cancelled,error,size] of [[true,'',100],[false,'Encoder permission denied',100],[true,'Encoder failed during cancellation',100],[false,'',0]]){
        app.cancelled=cancelled;app.chunks=[{size}];created=[];statuses=[];ui.downloadLink.hidden=false;
        expectedStream=cancelled?null:{};const before=cleaned;finishExport(expectedStream,true,error);
        assert(cleaned===before+1,'failed finishExport must clean up original stream once, including null');
        assert(created.length===0&&ui.downloadLink.hidden===true,'cancelled/error/empty export must not expose a new download');
        assert(app.chunks.length===0,'cancelled/error/empty export must discard partial chunks');
        const last=statuses.at(-1);
        assert(statuses.length===1&&last&&(error?last[0].includes(error)&&last[1]===true:cancelled?/cancel/i.test(last[0]):last[1]===true&&/empty|recording|zero|byte|kosong|rekaman|no.*(data|video)/i.test(last[0])),'finishExport must report actual error, cancellation or descriptive empty recording once and preserve it as final visible status; expected='+(error|| (cancelled?'Cancelled':'empty recording'))+' observed='+JSON.stringify(statuses));
      }
      assert(cleaned===6,'finishExport must always invoke cleanupExport');
    ''',
    'video_recording_chunk_callback': r'''
      const prior={size:7},chunk={size:20},chunks=[prior];
      const callback=makeRecordingChunkCallback(chunks);
      assert(typeof callback==='function','chunk factory must return an actual event callback');
      callback({data:null});callback({data:{size:0}});callback({data:chunk});
      assert(chunks.length===2&&chunks[0]===prior&&chunks[1]===chunk,'chunk callback must append only the original nonempty event.data to supplied array, preserving previous chunks');
    ''',
    'video_recording_finish_once': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      const stream={},state={message:'Actual failure',finished:false};
      finishRecordingOnce(stream,false,state);finishRecordingOnce(stream,false,state);
      assert(state.finished===true&&finished.length===1&&finished[0][0]===stream&&finished[0][1]===false&&finished[0][2]===state.message,'finishRecordingOnce must mark shared state and forward original values exactly once');
    ''',
    'video_recording_stop_callback': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      const stream={},state={message:'',finished:false};const callback=makeRecordingStopCallback(stream,false,state);
      assert(typeof callback==='function','stop factory must return an actual callback');
      state.message='Encoder error after callback creation';callback();callback();
      assert(finished.length===1&&finished[0][0]===stream&&finished[0][1]===false&&finished[0][2]===state.message,'stop callback must forward original stream, actual audio Boolean and current shared error message');
    ''',
    'video_recording_error_message': r'''
      for(const text of ['Actual encoder failure','Different recording failure']){
        const error=Object.freeze(new Error(text));const event=Object.freeze({error});
        assert(recordingErrorMessage(event)===text,'message helper must return actual event.error.message unchanged');
        assert(error.message===text,'message helper must not alter input error');
      }
      for(const [event,scenario] of [[{},'event.error absent'],[{error:null},'event.error null'],[{error:{message:''}},'event.error.message empty string']]){
        let fallback;try{fallback=recordingErrorMessage(event);}catch(error){assert(false,'Absent or null event.error must return a fallback without reading its message; observed throw='+error.message);}
        assert(typeof fallback==='string'&&fallback.length>0,scenario+' must return a nonempty fallback string; observed type='+typeof fallback+' value='+JSON.stringify(fallback));
      }
    ''',
    'video_settle_recording_error': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      const stream={};
      for(const initial of ['recording','paused','inactive']){
        finished=[];let stops=0;const state={message:'Actual failure',finished:false};
        const recorder={state:initial,stop(){stops++;this.state='inactive';}};
        settleRecordingError(recorder,stream,false,state);
        assert(initial==='inactive'?stops===0&&finished.length===1&&finished[0][0]===stream&&finished[0][1]===false&&finished[0][2]===state.message:stops===1&&finished.length===0,'settle must stop active recorder or finalize inactive recorder with original values, not both');
      }
    ''',
    'video_recording_error_callback': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      const stream={};
      for(const initial of ['recording','paused','inactive']){
        finished=[];const state={message:'',finished:false};let stops=0;
        const recorder={state:initial,stop(){stops++;this.state='inactive';}};
        const callback=makeRecordingErrorCallback(recorder,stream,true,state);
        assert(typeof callback==='function','error factory must return an actual event callback');
        callback({error:new Error('Actual encoder failure')});
        assert(state.message==='Actual encoder failure','error callback must retain original event.error.message in shared state');
        assert(initial==='inactive'?stops===0&&finished.length===1&&finished[0][0]===stream&&finished[0][1]===true&&finished[0][2]===state.message:stops===1&&finished.length===0,'active error must stop and let onstop finish; inactive error must finish directly once without stop');
      }
      finished=[];const missing={message:'',finished:false};
      makeRecordingErrorCallback({state:'inactive',stop(){throw new Error('Unexpected stop');}},stream,false,missing)({});
      assert(typeof missing.message==='string'&&missing.message.length>0&&finished.length===1&&finished[0][2]===missing.message,'missing event.error must produce a descriptive fallback and finalize once');
    ''',
    'video_export_recorder': r'''
      let finished=[];function finishExport(...args){finished.push(args);}
      let queued=[];
      class MediaRecorder{constructor(stream,options){this.stream=stream;this.mimeType=options.mimeType;this.state='inactive';this.stops=0;this.starts=0;}start(){this.starts++;this.state='recording';}stop(){if(this.state==='inactive')return;this.stops++;this.state='inactive';queued.push(()=>this.onstop());}}
      const window={MediaRecorder};globalThis.MediaRecorder=MediaRecorder;
      const stream={},prior={size:7};app.chunks=[prior];const originalChunks=app.chunks;
      const recorder=createExportRecorder(stream,'video/webm',true);
      assert(recorder===app.recorder&&recorder.stream===stream&&recorder.mimeType==='video/webm','createExportRecorder must store and return the real configured recorder');
      assert(recorder.starts===0&&recorder.state==='inactive','recorder helper must not start recording');
      recorder.ondataavailable({data:{size:0}});const chunk={size:20};recorder.ondataavailable({data:chunk});
      assert(app.chunks===originalChunks&&app.chunks.length===2&&app.chunks[0]===prior&&app.chunks[1]===chunk,'recorder must append original nonempty chunks without replacing previous data or array');
      recorder.onstop();recorder.onstop();assert(finished.length===1&&finished[0][0]===stream&&finished[0][1]===true&&!finished[0][2],'recorder stop must call finishExport once with stream and actual audio flag');
      for(const initial of ['recording','paused','inactive']){
        finished=[];queued=[];app.chunks=[];
        const failed=createExportRecorder(stream,'video/webm',false);failed.state=initial;
        failed.onerror({error:new Error('Encoder exploded')});
        assert(initial==='inactive'?failed.stops===0&&finished.length===1:failed.stops===1&&finished.length===0&&queued.length===1,'recorder must finish inactive error directly or wait for queued onstop after active error');
        for(const callback of queued)callback();
        failed.onstop();
        assert(finished.length===1&&finished[0][0]===stream&&finished[0][1]===false&&finished[0][2]==='Encoder exploded','recorder error must finalize exactly once with actual stream, audio flag and error');
      }
      finished=[];app.chunks=[];const fallback=createExportRecorder(stream,'video/webm',true);
      fallback.onerror({});fallback.onstop();
      assert(finished.length===1&&typeof finished[0][2]==='string'&&finished[0][2].length>0,'recorder error without error payload must report fallback once even with following stop');
    ''',
    'video_recording_end_test': r'''
      for(const [time,end,ended,cancelled,expected] of [[0,5,false,false,false],[4.96,5,false,false,false],[4.98,5,false,false,true],[1,5,true,false,true],[1,5,false,true,true]]){
        assert(recordingMustStop(time,end,ended,cancelled)===expected,'recording stop predicate must use actual cancellation, ended and selected end threshold');
      }
    ''',
    'video_recording_progress': r'''
      for(const [time,start,end,expected] of [[1,2,6,0],[2,2,6,0],[4,2,6,50],[6,2,6,100],[8,2,6,100],[1.33,0,3,44]]){
        assert(recordingProgress(time,start,end)===expected,'recording progress must clamp and round actual selected interval percentage; expected='+expected+' observed='+recordingProgress(time,start,end));
      }
    ''',
    'video_recording_stop_boundary': r'''
      for(const time of [3,5.98,6.1]){
        let stops=0;const recorder={stop(){stops++;}},video={currentTime:time};
        stopRecordingAtBoundary(recorder,video,6);
        assert(stops===1&&video.currentTime===(time>=5.975?6:time),'boundary stop must stop actual recorder once and only move video to trim end when threshold reached');
      }
    ''',
    'video_recording_paint_progress': r'''
      let paints=0;function paintFrame(){paints++;}
      const video={currentTime:2},label={textContent:''};
      for(const [time,expected] of [[2,0],[3,25],[4,50],[5.2,80]]){
        video.currentTime=time;const before=paints,result=paintRecordingProgress(video,label,2,6);
        assert(result===true&&paints===before+1&&label.textContent===expected+'%','paint/progress helper must paint once, show dynamic progress and return Boolean true; expected='+expected+'% observed='+label.textContent+' result='+String(result)+' paint calls='+String(paints-before));
        assert(video.currentTime===time,'paint/progress helper must preserve video time');
      }
    ''',
    'video_recording_step': r'''
      let paints=0,stops=0;function paintFrame(){paints++;}
      app.start=2;app.end=6;app.cancelled=false;app.recorder={state:'recording',stop(){stops++;this.state='inactive';}};
      ui.preview={currentTime:4,ended:false};ui.progressLabel={textContent:''};
      for(const [time,expected] of [[2,0],[3,25],[4,50],[5,75],[5.2,80]]){
        ui.preview.currentTime=time;const drawn=paints,result=paintRecordingStep();
        assert(result===true&&paints===drawn+1&&ui.progressLabel.textContent===expected+'%','active step must paint once, display dynamic selected progress and return true; expected label='+expected+'% observed label='+ui.progressLabel.textContent+' result='+String(result)+' paint calls='+String(paints-drawn));
      }
      for(const [state,time,ended,cancelled] of [['inactive',3,false,false],['recording',5.98,false,false],['recording',3,true,false],['recording',3,false,true]]){
        app.recorder.state=state;ui.preview.currentTime=time;ui.preview.ended=ended;app.cancelled=cancelled;const before=stops,drawn=paints;
        assert(paintRecordingStep()===false&&paints===drawn&&stops===before+(state==='inactive'?0:1),'inactive, ended or cancelled step must return false without painting and stop only active recorder');
      }
    ''',
    'video_export_frames': r'''
      let paints=0,queued=[],stops=0;
      function paintFrame(){paints++;}
      let lastHandle=0;function requestAnimationFrame(fn){queued.push(fn);lastHandle=lastHandle===0?37:0;return lastHandle;}
      ui.progressLabel={textContent:''};ui.preview={currentTime:2,ended:false};
      app.start=2;app.end=6;app.cancelled=false;app.recorder={state:'recording',stop(){stops++;this.state='inactive';}};
      watchExportFrames();assert(paints===1&&queued.length===1&&app.raf===lastHandle,'watchExportFrames must paint and store the actual scheduled animation handle');
      ui.preview.currentTime=4;queued.shift()();assert(paints===2&&/50/.test(ui.progressLabel.textContent)&&app.raf===lastHandle,'frame progress must reflect selected trim interval and preserve actual RAF handle including zero');
      ui.preview.currentTime=5.98;queued.shift()();assert(stops===1&&app.recorder.state==='inactive'&&ui.preview.currentTime===6&&queued.length===0,'frame loop must stop at selected trim end and stop scheduling');
      for(const [cancelled,ended] of [[true,false],[false,true]]){
        app.recorder.state='recording';app.cancelled=cancelled;ui.preview.ended=ended;ui.preview.currentTime=3;queued=[];const before=stops;
        watchExportFrames();assert(stops===before+1&&queued.length===0,'cancelled or ended video must stop recording without scheduling another frame');
      }
      queued=[];const drawn=paints,before=stops;watchExportFrames();assert(queued.length===0&&paints===drawn&&stops===before,'inactive recorder must not paint, stop or schedule');
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

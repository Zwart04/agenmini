"""Recorder API fixtures; evaluator-only, never supplied as application source."""

EXPORT_CASES = {
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
      supported.clear();let rejected=false;try{chooseWebMMime();}catch(error){rejected=!!error.message;}
      assert(rejected,'chooseWebMMime must reject when no WebM MIME is supported');
    ''',
    'video_export_seek': r'''
      const timers=new Map(),listeners=new Map();let nextTimer=1,time=0,assignError=false,writes=[];
      function setTimeout(fn,ms){const id=nextTimer++;timers.set(id,{fn,ms});return id;}
      function clearTimeout(id){timers.delete(id);}
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

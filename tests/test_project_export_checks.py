"""Checker reference implementations. Never read by model prompts or assembly."""
import json
from pathlib import Path

import pytest

from app import project_checks, project_parts


REFERENCES = {
    'video_audio_silent_status': "function reportSilentAudio(error){setStatus('Silent export: '+error.message);return false;}",
    'video_audio_require_tracks': "function requireExportAudioTracks(stream,destination){if(!addExportAudioTracks(stream,destination))throw new Error('No audio tracks');return true;}",
    'video_audio_track_membership': 'function hasExportAudioTrack(stream,track){const tracks=stream.getAudioTracks();return tracks.includes(track);}',
    'video_audio_single_track': 'function addSingleExportAudioTrack(stream,track){if(!stream.getAudioTracks().includes(track))stream.addTrack(track);}',
    'video_audio_source': 'function createExportAudioSource(context,video){return context.createMediaElementSource(video);}',
    'video_audio_destination': 'function createExportAudioDestination(context){return context.createMediaStreamDestination();}',
    'video_audio_targets': 'function connectExportAudioTargets(source,context,destination){source.connect(context.destination);source.connect(destination);}',
    'video_audio_context': "function getExportAudioContext(){if(app.audioContext)return app.audioContext;const Type=window.AudioContext||window.webkitAudioContext;if(!Type)throw new Error('No Web Audio');app.audioContext=new Type();return app.audioContext;}",
    'video_audio_connections': 'function connectExportAudio(context,video){if(!app.audioSource){app.audioSource=context.createMediaElementSource(video);app.audioDest=context.createMediaStreamDestination();app.audioSource.connect(context.destination);app.audioSource.connect(app.audioDest);}return app.audioDest;}',
    'video_audio_tracks': 'function addExportAudioTracks(stream,destination){const tracks=destination.stream.getAudioTracks();for(const track of tracks)if(!stream.getAudioTracks().includes(track))stream.addTrack(track);return tracks.length>0;}',
    'video_seek_timer_factory': "function makeSeekTimer(job){return setTimeout(()=>failSeekJob(job,new Error('Seek timeout')),5000);}",
    'video_seek_callback': 'function makeSeekCallback(job){return ()=>completeSeekJob(job);}',
    'video_seek_store': 'function storeSeekCallback(job){job.onSeeked=makeSeekCallback(job);}',
    'video_seek_listen': "function listenSeekCallback(job){job.video.addEventListener('seeked',job.onSeeked);}",
    'video_seek_job': 'function makeSeekJob(video,resolve,reject){return {video,resolve,reject,timer:null,onSeeked:null};}',
    'video_seek_clear': "function clearSeekJob(job){if(job.timer!==null)clearTimeout(job.timer);if(job.onSeeked!==null)job.video.removeEventListener('seeked',job.onSeeked);job.timer=null;job.onSeeked=null;}",
    'video_seek_complete': 'function completeSeekJob(job){clearSeekJob(job);job.resolve();}',
    'video_seek_fail': 'function failSeekJob(job,error){clearSeekJob(job);job.reject(error);}',
    'video_seek_register': "function registerSeekEvent(job){job.onSeeked=()=>completeSeekJob(job);job.video.addEventListener('seeked',job.onSeeked);}",
    'video_seek_timer': "function scheduleSeekTimeout(job){job.timer=setTimeout(()=>failSeekJob(job,new Error('Seek timeout')),5000);}",
    'video_seek_assign': "function assignSeekTarget(job,target){try{job.video.currentTime=target;}catch(error){failSeekJob(job,error);}}",
    'video_seek_arm': "function armSeekJob(job,target){registerSeekEvent(job);scheduleSeekTimeout(job);assignSeekTarget(job,target);}",
    'video_export_mime': """function chooseWebMMime(){
      for(const mime of ['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'])if(MediaRecorder.isTypeSupported(mime))return mime;
      throw new Error('WebM is unsupported');
    }""",
    'video_export_seek': """async function seekExportStart(){
      if(Math.abs(ui.preview.currentTime-app.start)<.02)return;
      await new Promise((resolve,reject)=>{
        let timer;const clear=()=>{clearTimeout(timer);ui.preview.removeEventListener('seeked',done);};
        const done=()=>{clear();resolve();};
        ui.preview.addEventListener('seeked',done,{once:true});
        timer=setTimeout(()=>{clear();reject(new Error('Seek timeout'));},5000);
        try{ui.preview.currentTime=app.start;}catch(error){clear();reject(error);}
      });
    }""",
    'video_export_audio': """async function attachExportAudio(stream){
      try{
        const Type=window.AudioContext||window.webkitAudioContext;
        if(!Type)throw new Error('No Web Audio');
        if(!app.audioContext)app.audioContext=new Type();
        if(!app.audioSource){app.audioSource=app.audioContext.createMediaElementSource(ui.preview);app.audioDest=app.audioContext.createMediaStreamDestination();app.audioSource.connect(app.audioContext.destination);app.audioSource.connect(app.audioDest);}
        await app.audioContext.resume();
        const tracks=app.audioDest.stream.getAudioTracks();for(const track of tracks)stream.addTrack(track);
        if(!tracks.length)throw new Error('No audio track');
        return true;
      }catch(error){setStatus('Silent export: '+error.message);return false;}
    }""",
    'video_stop_export_tracks': """function stopExportVideoTracks(stream){
      if(stream)for(const track of stream.getVideoTracks())track.stop();
    }""",
    'video_cancel_export_frame': """function cancelExportFrame(handle){
      if(handle!==null)cancelAnimationFrame(handle);
    }""",
    'video_export_cleanup': """function cleanupExport(stream){
      if(stream)for(const track of stream.getVideoTracks())track.stop();
      if(app.raf!==null)cancelAnimationFrame(app.raf);app.raf=null;
      ui.preview.pause();ui.playBtn.textContent='Play';ui.progressLabel.textContent='';setBusy(false);
    }""",
    'video_export_discard': "function discardExportResult(message,isError){app.chunks=[];ui.downloadLink.hidden=true;setStatus(message,isError);}",
    'video_recorded_blob': "function createRecordedBlob(){return new Blob(app.chunks,{type:app.recorder.mimeType});}",
    'video_recording_url': "function replaceRecordingURL(blob,previousURL){if(previousURL)URL.revokeObjectURL(previousURL);return URL.createObjectURL(blob);}",
    'video_recording_link': "function exposeRecordingLink(link,url){link.href=url;link.download='clip-mini.webm';link.hidden=false;}",
    'video_recording_status': "function reportRecordingReady(size,audioEnabled){setStatus('Export ready: '+size+' bytes, '+(audioEnabled?'audio':'silent'));}",
    'video_publish_recording': """function publishRecordedBlob(blob,audioEnabled){
      if(app.downloadURL)URL.revokeObjectURL(app.downloadURL);app.downloadURL=URL.createObjectURL(blob);
      ui.downloadLink.href=app.downloadURL;ui.downloadLink.download='clip-mini.webm';ui.downloadLink.hidden=false;
      setStatus('Export ready: '+blob.size+' bytes, '+(audioEnabled?'audio':'silent'));
    }""",
    'video_export_finish': """function finishExport(stream,audioEnabled,errorMessage){
      cleanupExport(stream);
      if(errorMessage||app.cancelled){app.chunks=[];ui.downloadLink.hidden=true;setStatus(errorMessage||'Cancelled',!!errorMessage);return;}
      const blob=new Blob(app.chunks,{type:app.recorder.mimeType});
      if(!blob.size){app.chunks=[];ui.downloadLink.hidden=true;setStatus('Empty export',true);return;}
      if(app.downloadURL)URL.revokeObjectURL(app.downloadURL);app.downloadURL=URL.createObjectURL(blob);
      ui.downloadLink.href=app.downloadURL;ui.downloadLink.download='clip-mini.webm';ui.downloadLink.hidden=false;
      setStatus('Export ready: '+blob.size+' bytes, '+(audioEnabled?'audio':'silent'));
    }""",
    'video_recording_chunk_callback': "function makeRecordingChunkCallback(chunks){return event=>{if(event.data&&event.data.size>0)chunks.push(event.data);};}",
    'video_recording_finish_once': "function finishRecordingOnce(stream,audioEnabled,errorState){if(errorState.finished)return;errorState.finished=true;finishExport(stream,audioEnabled,errorState.message);}",
    'video_recording_stop_callback': "function makeRecordingStopCallback(stream,audioEnabled,errorState){return ()=>finishRecordingOnce(stream,audioEnabled,errorState);}",
    'video_recording_error_message': "function recordingErrorMessage(event){return event.error?.message||'Recording failed';}",
    'video_settle_recording_error': "function settleRecordingError(recorder,stream,audioEnabled,errorState){if(recorder.state==='inactive')finishRecordingOnce(stream,audioEnabled,errorState);else recorder.stop();}",
    'video_recording_error_callback': """function makeRecordingErrorCallback(recorder,stream,audioEnabled,errorState){
      return event=>{errorState.message=event.error?.message||'Recording failed';if(recorder.state!=='inactive')recorder.stop();else finishRecordingOnce(stream,audioEnabled,errorState);};
    }""",
    'video_export_recorder': """function createExportRecorder(stream,mime,audioEnabled){
      const recorder=new MediaRecorder(stream,{mimeType:mime});app.recorder=recorder;let failure='',done=false;
      const finish=()=>{if(done)return;done=true;finishExport(stream,audioEnabled,failure);};
      recorder.ondataavailable=event=>{if(event.data&&event.data.size)app.chunks.push(event.data);};
      recorder.onstop=finish;
      recorder.onerror=event=>{failure=event.error?.message||'Recording failed';if(recorder.state!=='inactive')recorder.stop();else finish();};
      return recorder;
    }""",
    'video_recording_end_test': 'function recordingMustStop(time,end,ended,cancelled){return cancelled||ended||time>=end-.025;}',
    'video_recording_progress': 'function recordingProgress(time,start,end){return Math.max(0,Math.min(100,Math.round((time-start)/(end-start)*100)));}',
    'video_recording_stop_boundary': 'function stopRecordingAtBoundary(recorder,video,end){if(video.currentTime>=end-.025)video.currentTime=end;recorder.stop();}',
    'video_recording_paint_progress': "function paintRecordingProgress(video,label,start,end){paintFrame();label.textContent=recordingProgress(video.currentTime,start,end)+'%';return true;}",
    'video_recording_step': """function paintRecordingStep(){
      if(app.recorder.state!=='recording')return false;
      if(recordingMustStop(ui.preview.currentTime,app.end,ui.preview.ended,app.cancelled)){stopRecordingAtBoundary(app.recorder,ui.preview,app.end);return false;}
      paintFrame();ui.progressLabel.textContent=recordingProgress(ui.preview.currentTime,app.start,app.end)+'%';return true;
    }""",
    'video_export_frames': """function watchExportFrames(){
      function frame(){
        if(app.recorder.state!=='recording')return;
        if(app.cancelled||ui.preview.ended||ui.preview.currentTime>=app.end-.025){if(!app.cancelled)ui.preview.currentTime=app.end;app.recorder.stop();return;}
        paintFrame();ui.progressLabel.textContent=Math.round(Math.max(0,Math.min(100,(ui.preview.currentTime-app.start)/(app.end-app.start)*100)))+'%';app.raf=requestAnimationFrame(frame);
      }frame();
    }""",
    'video_export_orchestration': """async function exportVideo(){
      if(!app.loaded||app.busy)return;if(!validateTrim())return;let stream=null;
      try{
        if(typeof MediaRecorder==='undefined'||!HTMLCanvasElement.prototype.captureStream)throw new Error('Recording unsupported');
        const mime=chooseWebMMime();app.cancelled=false;app.chunks=[];setBusy(true);ui.downloadLink.hidden=true;
        prepareCanvas();await seekExportStart();paintFrame();stream=app.canvas.captureStream(24);
        const audio=await attachExportAudio(stream),recorder=createExportRecorder(stream,mime,audio);recorder.start();await ui.preview.play();watchExportFrames();
      }catch(error){if(app.recorder&&app.recorder.state!=='inactive'){app.recorder.onstop=null;app.recorder.stop();}finishExport(stream,false,error.message);}
    }""",
}

REFERENCES['video_export_wait']=REFERENCES['video_export_seek'].replace(
    'seekExportStart()', 'waitForVideoTime(video,target)').replace('ui.preview','video').replace('app.start','target')


@pytest.mark.asyncio
@pytest.mark.parametrize('check', list(REFERENCES))
async def test_export_fixtures_accept_working_api_lifecycle(check):
    source=REFERENCES[check]
    if check=='video_seek_arm':source='\n'.join(REFERENCES[name] for name in ('video_seek_register','video_seek_timer','video_seek_assign'))+'\n'+source
    if check in ('video_recording_stop_callback','video_recording_error_callback','video_settle_recording_error'):source=REFERENCES['video_recording_finish_once']+source
    if check=='video_recording_step':source='\n'.join(REFERENCES[name] for name in ['video_recording_end_test','video_recording_progress','video_recording_stop_boundary'])+source
    if check=='video_recording_paint_progress':source=REFERENCES['video_recording_progress']+source
    assert not await project_checks.inspect_helper(source, check)


@pytest.mark.asyncio
@pytest.mark.parametrize('check,old,new', [
    ('video_audio_silent_status', "'Silent export: '+error.message", 'error.message'),
    ('video_audio_silent_status', 'return false', 'throw error'),
    ('video_audio_require_tracks', 'if(!addExportAudioTracks(stream,destination))', 'if(false)'),
    ('video_audio_require_tracks', 'addExportAudioTracks(stream,destination)', 'addExportAudioTracks({},destination)'),
    ('video_audio_track_membership', 'return tracks.includes(track)', 'return tracks.length>0'),
    ('video_audio_track_membership', 'tracks.includes(track)', 'tracks.some(value=>value.kind===track.kind)'),
    ('video_audio_single_track', 'if(!stream.getAudioTracks().includes(track))', 'if(true)'),
    ('video_audio_single_track', 'stream.addTrack(track)', 'stream.addTrack({...track})'),
    ('video_audio_source', 'createMediaElementSource(video)', 'createMediaElementSource({...video})'),
    ('video_audio_source', 'return context.createMediaElementSource(video)', 'context.createMediaElementSource(video);return {}'),
    ('video_audio_destination', 'return context.createMediaStreamDestination()', 'context.createMediaStreamDestination();return {}'),
    ('video_audio_targets', 'source.connect(context.destination)', 'source.connect(context)'),
    ('video_audio_targets', 'source.connect(destination);', ''),
    ('video_audio_targets', 'source.connect(destination);', 'source.connect(destination);source.connect(destination);'),
    ('video_audio_context', 'if(app.audioContext)', 'if(false)'),
    ('video_audio_context', 'new Type()', 'Type'),
    ('video_audio_connections', 'if(!app.audioSource)', 'if(true)'),
    ('video_audio_connections', 'app.audioSource.connect(context.destination);', ''),
    ('video_audio_tracks', 'if(!stream.getAudioTracks().includes(track))', 'if(true)'),
    ('video_audio_tracks', 'stream.addTrack(track)', 'stream.addTrack({...track})'),
    ('video_audio_tracks', 'return tracks.length>0', 'return true'),
    ('video_seek_callback', 'return ()=>completeSeekJob(job)', 'return completeSeekJob(job)'),
    ('video_seek_store', 'job.onSeeked=makeSeekCallback(job)', 'makeSeekCallback(job)'),
    ('video_seek_store', 'makeSeekCallback(job)', 'makeSeekCallback({...job})'),
    ('video_seek_listen', "'seeked',job.onSeeked", "'timeupdate',job.onSeeked"),
    ('video_seek_listen', "'seeked',job.onSeeked", "'seeked',()=>job.onSeeked()"),
    ('video_seek_timer_factory', 'return setTimeout', 'setTimeout'),
    ('video_seek_timer_factory', '5000', '500'),
    ('video_seek_timer_factory', '()=>failSeekJob', 'failSeekJob'),
    ('video_seek_timer_factory', 'return setTimeout', 'return 37;setTimeout'),
    ('video_seek_job', 'timer:null', 'timer:0'),
    ('video_seek_clear', 'job.timer!==null', 'job.timer'),
    ('video_seek_complete', 'clearSeekJob(job);job.resolve();', 'job.resolve();clearSeekJob(job);'),
    ('video_seek_fail', 'job.reject(error)', 'job.reject(new Error("Other error"))'),
    ('video_seek_timer', '5000', '500'),
    ('video_seek_timer', 'job.timer=setTimeout', 'setTimeout'),
    ('video_seek_timer', 'job.timer=setTimeout', 'job.timer=37;setTimeout'),
    ('video_seek_register', 'job.onSeeked=()=>completeSeekJob(job)', 'job.onSeeked=completeSeekJob(job)'),
    ('video_seek_assign', 'failSeekJob(job,error)', 'throw error'),
    ('video_export_mime', "if(MediaRecorder.isTypeSupported(mime))", 'if(true)'),
    ('video_export_seek', "ui.preview.addEventListener('seeked',done,{once:true});", ''),
    ('video_export_seek', 'clearTimeout(timer);', ''),
    ('video_export_audio', 'if(!app.audioSource)', 'if(true)'),
    ('video_export_audio', "setStatus('Silent export: '+error.message);return false;", 'throw error;'),
    ('video_stop_export_tracks', 'stream.getVideoTracks()', 'stream.getTracks()'),
    ('video_stop_export_tracks', 'if(stream)', 'if(true)'),
    ('video_cancel_export_frame', 'handle!==null', 'handle'),
    ('video_cancel_export_frame', 'cancelAnimationFrame(handle)', 'cancelAnimationFrame(27)'),
    ('video_export_discard', 'app.chunks=[];', ''),
    ('video_export_discard', 'setStatus(message,isError)', "setStatus('Error',true)"),
    ('video_recorded_blob', 'new Blob(app.chunks,', 'new Blob([],'),
    ('video_recorded_blob', 'new Blob(app.chunks,', 'new Blob([app.chunks],'),
    ('video_recorded_blob', 'type:app.recorder.mimeType', "type:'video/webm'"),
    ('video_recording_url', 'URL.createObjectURL(blob)', "URL.createObjectURL({size:0})"),
    ('video_recording_url', 'URL.revokeObjectURL(previousURL)', 'URL.revokeObjectURL(null)'),
    ('video_recording_link', 'link.href=url', "link.href='blob:old'"),
    ('video_recording_link', 'link.hidden=false', 'link.hidden=true'),
    ('video_recording_status', "+size+", "+100+"),
    ('video_recording_status', "'audio':'silent'", "'audio':'audio'"),
    ('video_publish_recording', 'URL.createObjectURL(blob)', "URL.createObjectURL({size:0})"),
    ('video_publish_recording', 'blob.size', '100'),
    ('video_publish_recording', 'ui.downloadLink.hidden=false', 'ui.downloadLink.hidden=true'),
    ('video_publish_recording', 'ui.downloadLink.href=app.downloadURL;', 'ui.downloadLink={};ui.downloadLink.href=app.downloadURL;'),
    ('video_publish_recording', 'URL.revokeObjectURL(app.downloadURL)', 'URL.revokeObjectURL(null)'),
    ('video_export_cleanup', 'stream.getVideoTracks()', 'stream.getTracks()'),
    ('video_export_cleanup', 'app.raf!==null', 'app.raf'),
    ('video_export_finish', 'new Blob(app.chunks,', 'new Blob([],'),
    ('video_export_finish', "ui.downloadLink.href=app.downloadURL", 'ui.downloadLink.href=app.objectURL'),
    ('video_export_finish', 'ui.downloadLink.hidden=true;', ''),
    ('video_recording_chunk_callback', 'event.data.size>0', 'event.data.length>0'),
    ('video_recording_chunk_callback', 'chunks.push(event.data)', 'chunks.push({data:event.data})'),
    ('video_recording_finish_once', 'errorState.finished=true;', ''),
    ('video_recording_stop_callback', 'finishRecordingOnce(stream,audioEnabled,errorState)', "finishRecordingOnce(stream,audioEnabled,{message:'',finished:false})"),
    ('video_recording_stop_callback', 'return ()=>finishRecordingOnce', 'return finishRecordingOnce'),
    ('video_recording_error_message', 'event.error?.message', 'event.error.message'),
    ('video_recording_error_message', 'event.error?.message', "'Fake error'"),
    ('video_settle_recording_error', "recorder.state==='inactive'", 'true'),
    ('video_settle_recording_error', 'finishRecordingOnce(stream,audioEnabled,errorState)', 'finishRecordingOnce({},audioEnabled,errorState)'),
    ('video_recording_error_callback', "recorder.state!=='inactive'", 'true'),
    ('video_recording_error_callback', 'event.error?.message', 'event.error.message'),
    ('video_recording_error_callback', 'if(recorder.state', 'finishExport(stream,audioEnabled,errorState.message);if(recorder.state'),
    ('video_export_recorder', 'event.data&&event.data.size', 'event.data'),
    ('video_recording_end_test', 'cancelled||ended', 'cancelled&&ended'),
    ('video_recording_end_test', 'end-.025', 'end+1'),
    ('video_recording_progress', '(end-start)', 'end'),
    ('video_recording_progress', 'Math.max(0,Math.min(100,', 'Math.max(-100,Math.min(200,'),
    ('video_recording_stop_boundary', 'if(video.currentTime>=end-.025)', 'if(true)'),
    ('video_recording_stop_boundary', 'recorder.stop();', ''),
    ('video_recording_paint_progress', 'paintFrame();', ''),
    ('video_recording_paint_progress', 'recordingProgress(video.currentTime,start,end)', '50'),
    ('video_recording_paint_progress', "+'%'", "+''"),
    ('video_recording_paint_progress', 'return true;', ''),
    ('video_recording_step', "app.recorder.state!=='recording'", "app.recorder.state==='recording'"),
    ('video_recording_step', "+'%'", "+''"),
    ('video_recording_step', 'recordingProgress(ui.preview.currentTime,app.start,app.end)', '50'),
    ('video_export_frames', 'app.end-.025', 'app.end+1'),
    ('video_export_orchestration', 'recorder.start();await ui.preview.play();', 'await ui.preview.play();recorder.start();'),
])
async def test_export_fixtures_reject_broken_behavior(check, old, new):
    assert old in REFERENCES[check]
    source=REFERENCES[check].replace(old,new)
    if check in ('video_recording_stop_callback','video_recording_error_callback','video_settle_recording_error'):source=REFERENCES['video_recording_finish_once']+source
    if check=='video_recording_step':source='\n'.join(REFERENCES[name] for name in ['video_recording_end_test','video_recording_progress','video_recording_stop_boundary'])+source
    if check=='video_recording_paint_progress':source=REFERENCES['video_recording_progress']+source
    assert await project_checks.inspect_helper(source, check)


@pytest.mark.asyncio
async def test_seek_jobs_compose_with_full_event_timeout_and_cleanup_cases():
    workers='\n'.join(REFERENCES[name] for name in (
        'video_seek_job','video_seek_clear','video_seek_complete','video_seek_fail',
        'video_seek_register','video_seek_timer','video_seek_assign','video_seek_arm'))
    wait='async function waitForVideoTime(video,target){if(Math.abs(video.currentTime-target)<.02)return;return new Promise((resolve,reject)=>{const job=makeSeekJob(video,resolve,reject);armSeekJob(job,target);});}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait,'video_export_wait')
    caller='async function seekExportStart(){return waitForVideoTime(ui.preview,app.start);}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait+'\n'+caller,'video_export_seek')
    assert await project_checks.inspect_helper(workers.replace('clearTimeout(job.timer);','')+'\n'+wait,'video_export_wait')
    reversed_order=workers.replace('registerSeekEvent(job);scheduleSeekTimeout(job);','scheduleSeekTimeout(job);registerSeekEvent(job);')
    assert await project_checks.inspect_helper(reversed_order,'video_seek_arm')


@pytest.mark.asyncio
async def test_audio_workers_preserve_full_context_reuse_and_silent_failure_cases():
    names=('video_audio_context','video_audio_connections','video_audio_tracks')
    workers='\n'.join(REFERENCES[name] for name in names)
    wrapper="async function attachExportAudio(stream){try{const context=getExportAudioContext();const destination=connectExportAudio(context,ui.preview);await context.resume();if(!addExportAudioTracks(stream,destination))throw new Error('No tracks');return true;}catch(error){setStatus('Silent export: '+error.message);return false;}}"
    assert not await project_checks.inspect_helper(workers+'\n'+wrapper,'video_export_audio')
    assert await project_checks.inspect_helper(workers.replace('if(!app.audioSource)','if(true)')+'\n'+wrapper,'video_export_audio')
    assert await project_checks.inspect_helper(workers+'\n'+wrapper.replace('await context.resume();',''),'video_export_audio')
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text(encoding='utf-8'))
    audio=next(part for part in recipe['parts'] if part.get('functions')==['attachExportAudio'])
    assert set(audio['behavior_dependencies'])=={'getExportAudioContext','connectExportAudio','addExportAudioTracks','createExportAudioSource','createExportAudioDestination','connectExportAudioTargets','addSingleExportAudioTrack','hasExportAudioTrack','requireExportAudioTracks','reportSilentAudio'}


@pytest.mark.asyncio
async def test_audio_fallback_workers_compose_with_complete_export_lifecycle():
    workers='\n'.join(REFERENCES[name] for name in ('video_audio_context','video_audio_connections','video_audio_tracks','video_audio_silent_status','video_audio_require_tracks'))
    wrapper='async function attachExportAudio(stream){try{const context=getExportAudioContext();const destination=connectExportAudio(context,ui.preview);await context.resume();requireExportAudioTracks(stream,destination);return true;}catch(error){return reportSilentAudio(error);}}'
    assert not await project_checks.inspect_helper(workers+'\n'+wrapper,'video_export_audio')
    assert await project_checks.inspect_helper(workers+'\n'+wrapper.replace('return reportSilentAudio(error);','throw error;'),'video_export_audio')
    assert await project_checks.inspect_helper(workers+'\n'+wrapper.replace('requireExportAudioTracks(stream,destination);',''),'video_export_audio')


@pytest.mark.asyncio
async def test_membership_and_single_track_workers_retain_complete_attachment_checks():
    membership=REFERENCES['video_audio_track_membership']
    single='function addSingleExportAudioTrack(stream,track){if(hasExportAudioTrack(stream,track))return;stream.addTrack(track);}'
    assert not await project_checks.inspect_helper(membership+'\n'+single,'video_audio_single_track')
    caller='function addExportAudioTracks(stream,destination){const tracks=destination.stream.getAudioTracks();for(const track of tracks)addSingleExportAudioTrack(stream,track);return tracks.length>0;}'
    assert not await project_checks.inspect_helper(membership+'\n'+single+'\n'+caller,'video_audio_tracks')
    assert await project_checks.inspect_helper(membership+'\n'+single.replace('if(hasExportAudioTrack(stream,track))return;',''),'video_audio_single_track')


@pytest.mark.asyncio
async def test_audio_factory_workers_compose_without_changing_full_export_audio_cases():
    factories='\n'.join(REFERENCES[name] for name in ('video_audio_source','video_audio_destination','video_audio_targets'))
    connection='function connectExportAudio(context,video){if(app.audioSource)return app.audioDest;app.audioSource=createExportAudioSource(context,video);app.audioDest=createExportAudioDestination(context);connectExportAudioTargets(app.audioSource,context,app.audioDest);return app.audioDest;}'
    assert not await project_checks.inspect_helper(factories+'\n'+connection,'video_audio_connections')
    workers=REFERENCES['video_audio_context']+'\n'+REFERENCES['video_audio_tracks']+'\n'+factories+'\n'+connection
    wrapper="async function attachExportAudio(stream){try{const context=getExportAudioContext();const destination=connectExportAudio(context,ui.preview);await context.resume();if(!addExportAudioTracks(stream,destination))throw new Error('No tracks');return true;}catch(error){setStatus('Silent export: '+error.message);return false;}}"
    assert not await project_checks.inspect_helper(workers+'\n'+wrapper,'video_export_audio')
    assert await project_checks.inspect_helper(workers.replace('app.audioSource=createExportAudioSource','createExportAudioSource')+'\n'+wrapper,'video_export_audio')


@pytest.mark.asyncio
async def test_single_track_worker_composes_with_full_audio_attachment_lifecycle():
    helper=REFERENCES['video_audio_single_track']
    caller='function addExportAudioTracks(stream,destination){const tracks=destination.stream.getAudioTracks();for(const track of tracks)addSingleExportAudioTrack(stream,track);return tracks.length>0;}'
    assert not await project_checks.inspect_helper(helper+'\n'+caller,'video_audio_tracks')
    workers=REFERENCES['video_audio_context']+'\n'+REFERENCES['video_audio_connections']+'\n'+helper+'\n'+caller
    wrapper="async function attachExportAudio(stream){try{const context=getExportAudioContext();const destination=connectExportAudio(context,ui.preview);await context.resume();if(!addExportAudioTracks(stream,destination))throw new Error('No tracks');return true;}catch(error){setStatus('Silent export: '+error.message);return false;}}"
    assert not await project_checks.inspect_helper(workers+'\n'+wrapper,'video_export_audio')
    assert await project_checks.inspect_helper(helper+'\n'+caller.replace('addSingleExportAudioTrack(stream,track);',''),'video_audio_tracks')


@pytest.mark.asyncio
async def test_track_attachment_diagnostic_names_actual_missing_side_effect():
    source='function addExportAudioTracks(stream,destination){return destination.stream.getAudioTracks().length>0;}'
    errors=await project_checks.inspect_helper(source,'video_audio_tracks')
    assert any('expected additions=2 observed=0' in error for error in errors)
    assert not any('must not be duplicated' in error for error in errors)
    assert not any('must return Boolean true' in error for error in errors)


@pytest.mark.asyncio
async def test_single_track_diagnostics_distinguish_existing_identity_and_wrong_argument():
    duplicate='function addSingleExportAudioTrack(stream,track){stream.addTrack(track);}'
    errors=await project_checks.inspect_helper(duplicate,'video_audio_single_track')
    assert any('supplied track already present: do not add it again' in error and 'expected additions=0 observed=1' in error for error in errors)
    copied='function addSingleExportAudioTrack(stream,track){if(!stream.getAudioTracks().includes(track))stream.addTrack({...track});}'
    errors=await project_checks.inspect_helper(copied,'video_audio_single_track')
    assert any('must receive original supplied track object' in error and 'same identity=false' in error for error in errors)
    assert not any('expected additions=1 observed=1' in error for error in errors)


@pytest.mark.asyncio
async def test_audio_context_diagnostics_isolate_constructor_support_from_cache_failure():
    primary_only='function getExportAudioContext(){if(app.audioContext)return app.audioContext;if(!window.AudioContext)throw new Error("AudioContext not supported");app.audioContext=new window.AudioContext();return app.audioContext;}'
    errors=await project_checks.inspect_helper(primary_only,'video_audio_context')
    assert any('must accept available window.webkitAudioContext' in error and 'AudioContext not supported' in error for error in errors)
    no_cache='function getExportAudioContext(){if(app.audioContext)return app.audioContext;const Type=window.AudioContext||window.webkitAudioContext;if(!Type)throw new Error("No audio");return new Type();}'
    errors=await project_checks.inspect_helper(no_cache,'video_audio_context')
    assert any('store actual instance in app.audioContext and reuse it' in error for error in errors)
    assert not any('must accept available window.webkitAudioContext' in error for error in errors)
    assert all(error.startswith('Helper behavior failed:') for error in errors)


@pytest.mark.asyncio
async def test_audio_fallback_diagnostic_separates_recoverable_resume_failure_from_rethrow():
    source=REFERENCES['video_export_audio'].replace("setStatus('Silent export: '+error.message);return false;","setStatus('Silent export: '+error.message);throw error;")
    errors=await project_checks.inspect_helper(source,'video_export_audio')
    assert any('recoverable audio resume failure must return false without rejecting export' in error and 'Audio permission denied' in error for error in errors)
    assert all(error.startswith('Helper behavior failed:') for error in errors)


@pytest.mark.asyncio
async def test_audio_fallback_diagnostic_requires_actual_false_and_silent_status_for_empty_tracks():
    source=REFERENCES['video_export_audio'].replace("if(!tracks.length)throw new Error('No audio track');",'')
    errors=await project_checks.inspect_helper(source,'video_export_audio')
    assert any('empty audio destination must return Boolean false' in error and 'result=true' in error for error in errors)
    assert any('empty audio destination must report explicit silent export' in error for error in errors)


@pytest.mark.asyncio
async def test_callback_workers_compose_with_unmodified_seek_lifecycle_cases():
    callback_workers='\n'.join(REFERENCES[name] for name in ('video_seek_callback','video_seek_store','video_seek_listen'))
    register='function registerSeekEvent(job){storeSeekCallback(job);listenSeekCallback(job);}'
    assert not await project_checks.inspect_helper(callback_workers+'\n'+register,'video_seek_register')
    workers='\n'.join(REFERENCES[name] for name in ('video_seek_job','video_seek_clear','video_seek_complete','video_seek_fail',
        'video_seek_timer','video_seek_assign','video_seek_arm'))+'\n'+callback_workers+'\n'+register
    wait='async function waitForVideoTime(video,target){if(Math.abs(video.currentTime-target)<.02)return;return new Promise((resolve,reject)=>{const job=makeSeekJob(video,resolve,reject);armSeekJob(job,target);});}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait,'video_export_wait')
    caller='async function seekExportStart(){return waitForVideoTime(ui.preview,app.start);}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait+'\n'+caller,'video_export_seek')
    assert await project_checks.inspect_helper(callback_workers+'\n'+register.replace('storeSeekCallback(job);listenSeekCallback(job);','listenSeekCallback(job);storeSeekCallback(job);'),'video_seek_register')
    assert await project_checks.inspect_helper(workers.replace('job.onSeeked=makeSeekCallback(job);','makeSeekCallback(job);')+'\n'+wait,'video_export_wait')
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text())
    parts={part['functions'][0]:part for part in recipe['parts'] if part.get('functions')}
    required={'makeSeekCallback','storeSeekCallback','listenSeekCallback'}
    for fn in ('registerSeekEvent','armSeekJob','waitForVideoTime','seekExportStart'):
        assert required<=set(parts[fn]['behavior_dependencies'])


@pytest.mark.asyncio
async def test_timer_factory_and_storage_compose_with_original_seek_cases():
    timer=REFERENCES['video_seek_timer_factory']+'\nfunction scheduleSeekTimeout(job){job.timer=makeSeekTimer(job);}'
    assert not await project_checks.inspect_helper(timer,'video_seek_timer')
    assert await project_checks.inspect_helper(timer.replace('job.timer=makeSeekTimer(job)','makeSeekTimer(job)'),'video_seek_timer')
    workers='\n'.join(REFERENCES[name] for name in ('video_seek_job','video_seek_clear','video_seek_complete','video_seek_fail',
        'video_seek_register','video_seek_assign','video_seek_arm'))+'\n'+timer
    wait='async function waitForVideoTime(video,target){if(Math.abs(video.currentTime-target)<.02)return;return new Promise((resolve,reject)=>{const job=makeSeekJob(video,resolve,reject);armSeekJob(job,target);});}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait,'video_export_wait')
    caller='async function seekExportStart(){return waitForVideoTime(ui.preview,app.start);}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait+'\n'+caller,'video_export_seek')
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text())
    parts={part['functions'][0]:part for part in recipe['parts'] if part.get('functions')}
    for fn in ('scheduleSeekTimeout','armSeekJob','waitForVideoTime','seekExportStart'):
        assert 'makeSeekTimer' in parts[fn]['behavior_dependencies']


@pytest.mark.asyncio
async def test_seek_assignment_diagnostics_distinguish_expected_behavior_from_model_exception():
    rejects_zero='function assignSeekTarget(job,target){if(target<=0)throw new Error("target must be positive");try{job.video.currentTime=target;}catch(error){failSeekJob(job,error);}}'
    errors=await project_checks.inspect_helper(rejects_zero,'video_seek_assign')
    assert any('assignSeekTarget(0) must accept already validated seconds including zero' in error and 'target must be positive' in error for error in errors)
    assert all(error.startswith('Helper behavior failed:') for error in errors)
    no_catch='function assignSeekTarget(job,target){job.video.currentTime=target;}'
    errors=await project_checks.inspect_helper(no_catch,'video_seek_assign')
    assert any('must catch a video assignment exception and delegate actual Error to failSeekJob' in error and 'Actual assignment denied' in error for error in errors)
    assert all(error.startswith('Helper behavior failed:') for error in errors)


@pytest.mark.asyncio
async def test_seek_arm_reports_absent_registration_before_fixture_callback_invocation():
    errors=await project_checks.inspect_helper(
        'function armSeekJob(job,target){try{job.video.currentTime=target;}catch(error){failSeekJob(job,error);}}', 'video_seek_arm')
    assert any('assign an actual seeked callback' in error for error in errors)
    assert any('immediately call browser setTimeout' in error for error in errors)
    assert all(error.startswith('Helper behavior failed:') for error in errors)


def test_export_recipe_is_only_instructions_and_uses_all_lifecycle_checks():
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text(encoding='utf-8'))
    parts=[part for part in recipe['parts'] if any(check in REFERENCES for check in part.get('behavior_checks',[]))]
    assert len(parts)==len(REFERENCES)
    assert all(part['raw_source'] and part['include_html'] is False for part in parts)
    assert all('source' not in part for part in parts)
    assert not any(source in json.dumps(recipe) for source in REFERENCES.values())


def test_shared_reference_validation_uses_ast_not_comments_or_file_strings():
    prior='const app={start:0};const ui={preview:null};'
    source="function f(){const a='./app.js',b='ui.js';/* app.wrong;ui.wrong */return ui.preview;}"
    assert project_parts.js_shared_reference_errors(source,prior)==[]
    for access in ['app.bad','app["bad"]','ui.bad','ui["bad"]']:
        assert any('Undefined shared field' in error for error in project_parts.js_shared_reference_errors('function f(){return '+access+';}',prior))
    assert project_parts.parsed_js_contracts(source)=={'globals':{},'existing_functions':['function f()'],'shadowed_state':[]}


@pytest.mark.asyncio
async def test_selected_fixture_is_stdin_data_with_bounded_windows_command(monkeypatch):
    captured=[]
    async def sandbox(args,**options):
        captured.append((args,options))
        return '[kode keluar 0]\nbehavioral helper check passed'
    monkeypatch.setattr(project_checks.tools,'_run_sandboxed',sandbox)
    for check in ['video_canvas_frame','video_export_seek','video_export_orchestration']:
        assert not await project_checks.inspect_helper('model source',check)
    assert len({args[-1] for args,_ in captured})==1
    for args,options in captured:
        payload=json.loads(options['stdin'])
        assert payload['source']=='model source'
        assert payload['caseFixture']==project_checks.CASE_FIXTURES[payload['check']]
        assert len(' '.join(args))<30000
        assert options['timeout']==5 and options['project'] is True


def test_opt_in_preserves_only_complete_original_literal_dependency_response():
    helper='function chooseWebMMime(){for(const value of TYPES)if(MediaRecorder.isTypeSupported(value))return value;throw new Error("Unsupported");}'
    source='// Model-authored data\nconst TYPES=["video/webm;codecs=vp9,opus","video/webm"];\n'+helper
    item={'kind':'js','functions':['chooseWebMMime'],'behavior_checks':['video_export_mime'],'preserve_literal_constants':True}
    assert project_parts.select_model_helper(source,item)==source
    assert project_parts.select_model_helper(source,{**item,'preserve_literal_constants':False})==helper
    assert project_parts.select_model_helper(helper+'\nconst TYPES=["video/webm"];',item)==helper+'\nconst TYPES=["video/webm"];'
    for declaration in ['let TYPES=["video/webm"];','const TYPES=getTypes();','const TYPES=[readSecret()];',
                        'const TYPES=[...otherTypes];','const TYPES={value:"video/webm"};','const TYPES=/webm/;']:
        assert project_parts.select_model_helper(declaration+helper,item)==helper
    assert project_parts.select_model_helper(source+'\nrunExtra();',item)==helper
    assert project_parts.select_model_helper(source+'\nconst UNUSED=1;',item)==helper
    shadowed='function chooseWebMMime(){const TYPES=["inside"];return TYPES[0];}'
    assert project_parts.select_model_helper('const TYPES=["outside"];'+shadowed,item)==shadowed
    member='function chooseWebMMime(){return other.TYPES;}'
    assert project_parts.select_model_helper('const TYPES=["outside"];'+member,item)==member


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_literal_dependency_keeps_exact_model_bytes_and_replay_evidence(monkeypatch,tmp_path,backend):
    from app import llm, project_patches
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Codec','kind':'js','file':'app.js','functions':['chooseWebMMime'],
          'task':'Choose the first supported MIME; literal const data may accompany the helper.',
          'raw_source':True,'include_html':False,'preserve_literal_constants':True,'behavior_checks':['video_export_mime'],
          'state_writes':[],'relevant_fields':{'app':[],'ui':[]},'relevant_functions':[]}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    # Checker fixture: the model stub response, never real benchmark runtime.
    source='const TYPES=["video/webm;codecs=vp9,opus","video/webm;codecs=vp8,opus","video/webm"];\nfunction chooseWebMMime(){for(const type of TYPES)if(MediaRecorder.isTypeSupported(type))return type;throw new Error("Unsupported");}'
    async def model(messages,**options):
        assert source not in messages[1]['content']
        assert 'Complete const literal data' in messages[0]['content']
        assert 'Do not use or create any global state.' not in messages[0]['content']
        return {'content':source,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==source and value['raw_source']==source
            assert value['evidence']['sha256']==project_patches.digest(source)
            assert value['evidence']['raw_sha256']==project_patches.digest(source)
            cached=project_parts.reusable_part(value,{**item,'generation_contract_revision':2})
            assert cached and cached['content']==source
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)


@pytest.mark.asyncio
@pytest.mark.parametrize('omitted',[None,'stopExportVideoTracks(stream);','cancelExportFrame(app.raf);'])
async def test_export_cleanup_composes_actual_track_and_frame_helpers(omitted):
    source = REFERENCES['video_stop_export_tracks'] + REFERENCES['video_cancel_export_frame'] + """
      function cleanupExport(stream){
        stopExportVideoTracks(stream);cancelExportFrame(app.raf);app.raf=null;
        ui.preview.pause();ui.playBtn.textContent='Play';ui.progressLabel.textContent='';setBusy(false);
      }
    """
    if omitted:source=source.replace(omitted,'')
    errors=await project_checks.inspect_helper(source,'video_export_cleanup')
    assert bool(errors)==bool(omitted)


@pytest.mark.asyncio
@pytest.mark.parametrize('owner',['','window.','globalThis.'])
async def test_frame_cancel_accepts_actual_browser_global_api_spellings(owner):
    source=REFERENCES['video_cancel_export_frame'].replace('cancelAnimationFrame(handle)',owner+'cancelAnimationFrame(handle)')
    assert not await project_checks.inspect_helper(source,'video_cancel_export_frame')
    composite=REFERENCES['video_stop_export_tracks']+source+"""
      function cleanupExport(stream){
        stopExportVideoTracks(stream);cancelExportFrame(app.raf);app.raf=null;
        ui.preview.pause();ui.playBtn.textContent='Play';ui.progressLabel.textContent='';setBusy(false);
      }
    """
    assert not await project_checks.inspect_helper(composite,'video_export_cleanup')
    broken=source.replace(owner+'cancelAnimationFrame(handle)',owner+'cancelAnimationFrame(311)')
    assert await project_checks.inspect_helper(broken,'video_cancel_export_frame')


@pytest.mark.asyncio
@pytest.mark.parametrize('broken',[None,'missing_cleanup','wrong_stream','empty_publish','empty_boolean','lost_error','continue_after_error'])
async def test_export_finish_composes_actual_discard_blob_and_publish_helpers(broken):
    source='\n'.join(REFERENCES[name] for name in ['video_export_discard','video_recorded_blob','video_publish_recording'])+"""
      function finishExport(stream,audioEnabled,errorMessage){
        cleanupExport(stream);
        if(errorMessage){discardExportResult(errorMessage,true);return;}
        if(app.cancelled){discardExportResult('Cancelled',false);return;}
        const blob=createRecordedBlob();
        if(!blob.size){discardExportResult('Empty recording',true);return;}
        publishRecordedBlob(blob,audioEnabled);
      }
    """
    if broken=='missing_cleanup':source=source.replace('cleanupExport(stream);','')
    if broken=='wrong_stream':source=source.replace('cleanupExport(stream);','cleanupExport({});')
    if broken=='empty_publish':source=source.replace("if(!blob.size){discardExportResult('Empty recording',true);return;}",'')
    if broken=='empty_boolean':source=source.replace("discardExportResult('Empty recording',true)",'discardExportResult(false,true)')
    if broken=='lost_error':source=source.replace('discardExportResult(errorMessage,true)',"discardExportResult('Error',true)")
    if broken=='continue_after_error':source=source.replace('if(errorMessage){discardExportResult(errorMessage,true);return;}','if(errorMessage){discardExportResult(errorMessage,true);}')
    assert bool(await project_checks.inspect_helper(source,'video_export_finish'))==bool(broken)


@pytest.mark.asyncio
@pytest.mark.parametrize('parts',['app.chunks','[...app.chunks]','app.chunks.slice()'])
async def test_recorded_blob_accepts_flat_original_chunks_without_requiring_array_identity(parts):
    source=REFERENCES['video_recorded_blob'].replace('Blob(app.chunks,','Blob('+parts+',')
    assert not await project_checks.inspect_helper(source,'video_recorded_blob')
    composite=REFERENCES['video_export_finish'].replace('Blob(app.chunks,','Blob('+parts+',')
    assert not await project_checks.inspect_helper(composite,'video_export_finish')


@pytest.mark.asyncio
@pytest.mark.parametrize('omitted',[None,'exposeRecordingLink(ui.downloadLink,app.downloadURL);','reportRecordingReady(blob.size,audioEnabled);'])
async def test_publish_composes_actual_url_anchor_and_status_helpers(omitted):
    source='\n'.join(REFERENCES[name] for name in ['video_recording_url','video_recording_link','video_recording_status'])+"""
      function publishRecordedBlob(blob,audioEnabled){
        app.downloadURL=replaceRecordingURL(blob,app.downloadURL);
        exposeRecordingLink(ui.downloadLink,app.downloadURL);
        reportRecordingReady(blob.size,audioEnabled);
      }
    """
    if omitted:source=source.replace(omitted,'')
    assert bool(await project_checks.inspect_helper(source,'video_publish_recording'))==bool(omitted)
    if not omitted:
        composite=source+REFERENCES['video_export_discard']+REFERENCES['video_recorded_blob']+"""
          function finishExport(stream,audioEnabled,errorMessage){
            cleanupExport(stream);
            if(errorMessage){discardExportResult(errorMessage,true);return;}
            if(app.cancelled){discardExportResult('Cancelled',false);return;}
            const blob=createRecordedBlob();
            if(!blob.size){discardExportResult('Empty recording',true);return;}
            publishRecordedBlob(blob,audioEnabled);
          }
        """
        assert not await project_checks.inspect_helper(composite,'video_export_finish')


@pytest.mark.asyncio
@pytest.mark.parametrize('broken',[None,'snapshot_error','invoke_chunk_early','double_finish','wrong_message_target'])
async def test_recorder_factories_compose_with_deferred_stop_and_real_error_scopes(broken):
    source='\n'.join(REFERENCES[name] for name in ['video_recording_chunk_callback','video_recording_finish_once','video_recording_stop_callback','video_recording_error_message','video_settle_recording_error'])+"""
      function makeRecordingErrorCallback(recorder,stream,audioEnabled,errorState){
        return event=>{errorState.message=recordingErrorMessage(event);settleRecordingError(recorder,stream,audioEnabled,errorState);};
      }
      function createExportRecorder(stream,mime,audioEnabled){
        const recorder=new MediaRecorder(stream,{mimeType:mime});const errorState={message:'',finished:false};
        recorder.ondataavailable=makeRecordingChunkCallback(app.chunks);
        recorder.onstop=makeRecordingStopCallback(stream,audioEnabled,errorState);
        recorder.onerror=makeRecordingErrorCallback(recorder,stream,audioEnabled,errorState);
        app.recorder=recorder;return recorder;
      }
    """
    if broken=='snapshot_error':source=source.replace('()=>finishRecordingOnce(stream,audioEnabled,errorState)',"()=>finishRecordingOnce(stream,audioEnabled,{message:'',finished:false})")
    if broken=='invoke_chunk_early':source=source.replace('makeRecordingChunkCallback(app.chunks);','makeRecordingChunkCallback(app.chunks)();')
    if broken=='double_finish':source=source.replace('if(recorder.state', 'finishExport(stream,audioEnabled,errorState.message);if(recorder.state')
    if broken=='wrong_message_target':source=source.replace('errorState.message=recordingErrorMessage(event)','event.error.message=recordingErrorMessage(event)')
    assert bool(await project_checks.inspect_helper(source,'video_export_recorder'))==bool(broken)


@pytest.mark.asyncio
@pytest.mark.parametrize('broken',[None,'wrong_handle','invoke_callback','schedule_stopped'])
async def test_frame_loop_composes_actual_stop_progress_and_step_helpers(broken):
    source='\n'.join(REFERENCES[name] for name in ['video_recording_end_test','video_recording_progress','video_recording_stop_boundary','video_recording_paint_progress'])+"""
      function paintRecordingStep(){
        if(app.recorder.state!=='recording')return false;
        if(recordingMustStop(ui.preview.currentTime,app.end,ui.preview.ended,app.cancelled)){stopRecordingAtBoundary(app.recorder,ui.preview,app.end);return false;}
        paintRecordingProgress(ui.preview,ui.progressLabel,app.start,app.end);return true;
      }
      function watchExportFrames(){
        function frame(){if(paintRecordingStep())app.raf=requestAnimationFrame(frame);}
        frame();
      }
    """
    if broken=='wrong_handle':source=source.replace('app.raf=requestAnimationFrame(frame)','requestAnimationFrame(frame);app.raf=123')
    if broken=='invoke_callback':source=source.replace('requestAnimationFrame(frame)','requestAnimationFrame(frame())')
    if broken=='schedule_stopped':source=source.replace('if(paintRecordingStep())','paintRecordingStep();')
    assert bool(await project_checks.inspect_helper(source,'video_export_frames'))==bool(broken)

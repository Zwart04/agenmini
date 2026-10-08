"""Checker reference implementations. Never read by model prompts or assembly."""
import json
from pathlib import Path

import pytest

from app import project_checks, project_parts


REFERENCES = {
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
    'video_export_cleanup': """function cleanupExport(stream){
      if(stream)for(const track of stream.getVideoTracks())track.stop();
      if(app.raf!==null)cancelAnimationFrame(app.raf);app.raf=null;
      ui.preview.pause();ui.playBtn.textContent='Play';ui.progressLabel.textContent='';setBusy(false);
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
    'video_export_recorder': """function createExportRecorder(stream,mime,audioEnabled){
      const recorder=new MediaRecorder(stream,{mimeType:mime});app.recorder=recorder;let failure='';
      recorder.ondataavailable=event=>{if(event.data&&event.data.size)app.chunks.push(event.data);};
      recorder.onstop=()=>finishExport(stream,audioEnabled,failure);
      recorder.onerror=event=>{failure=event.error?.message||'Recording failed';if(recorder.state!=='inactive')recorder.stop();else finishExport(stream,audioEnabled,failure);};
      return recorder;
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


@pytest.mark.asyncio
@pytest.mark.parametrize('check', list(REFERENCES))
async def test_export_fixtures_accept_working_api_lifecycle(check):
    assert not await project_checks.inspect_helper(REFERENCES[check], check)


@pytest.mark.asyncio
@pytest.mark.parametrize('check,old,new', [
    ('video_export_mime', "if(MediaRecorder.isTypeSupported(mime))", 'if(true)'),
    ('video_export_seek', "ui.preview.addEventListener('seeked',done,{once:true});", ''),
    ('video_export_seek', 'clearTimeout(timer);', ''),
    ('video_export_audio', 'if(!app.audioSource)', 'if(true)'),
    ('video_export_audio', "setStatus('Silent export: '+error.message);return false;", 'throw error;'),
    ('video_export_cleanup', 'stream.getVideoTracks()', 'stream.getTracks()'),
    ('video_export_cleanup', 'app.raf!==null', 'app.raf'),
    ('video_export_finish', 'new Blob(app.chunks,', 'new Blob([],'),
    ('video_export_finish', "ui.downloadLink.href=app.downloadURL", 'ui.downloadLink.href=app.objectURL'),
    ('video_export_recorder', 'event.data&&event.data.size', 'event.data'),
    ('video_export_frames', 'app.end-.025', 'app.end+1'),
    ('video_export_orchestration', 'recorder.start();await ui.preview.play();', 'await ui.preview.play();recorder.start();'),
])
async def test_export_fixtures_reject_broken_behavior(check, old, new):
    assert old in REFERENCES[check]
    assert await project_checks.inspect_helper(REFERENCES[check].replace(old,new), check)


def test_export_recipe_is_only_instructions_and_uses_all_lifecycle_checks():
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text(encoding='utf-8'))
    parts=[part for part in recipe['parts'] if any(check in REFERENCES for check in part.get('behavior_checks',[]))]
    assert len(parts)==len(REFERENCES)
    assert all(part['raw_source'] and part['include_html'] is False for part in parts)
    assert all('source' not in part for part in parts)
    assert not any(source in json.dumps(recipe) for source in REFERENCES.values())


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

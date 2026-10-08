"""Checker reference implementations. Never read by model prompts or assembly."""
import json
from pathlib import Path

import pytest

from app import project_checks, project_parts


REFERENCES = {
    'video_seek_job': 'function makeSeekJob(video,resolve,reject){return {video,resolve,reject,timer:null,onSeeked:null};}',
    'video_seek_clear': "function clearSeekJob(job){if(job.timer!==null)clearTimeout(job.timer);if(job.onSeeked!==null)job.video.removeEventListener('seeked',job.onSeeked);job.timer=null;job.onSeeked=null;}",
    'video_seek_complete': 'function completeSeekJob(job){clearSeekJob(job);job.resolve();}',
    'video_seek_fail': 'function failSeekJob(job,error){clearSeekJob(job);job.reject(error);}',
    'video_seek_arm': "function armSeekJob(job,target){job.onSeeked=()=>completeSeekJob(job);job.video.addEventListener('seeked',job.onSeeked);job.timer=setTimeout(()=>failSeekJob(job,new Error('Seek timeout')),5000);try{job.video.currentTime=target;}catch(error){failSeekJob(job,error);}}",
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

REFERENCES['video_export_wait']=REFERENCES['video_export_seek'].replace(
    'seekExportStart()', 'waitForVideoTime(video,target)').replace('ui.preview','video').replace('app.start','target')


@pytest.mark.asyncio
@pytest.mark.parametrize('check', list(REFERENCES))
async def test_export_fixtures_accept_working_api_lifecycle(check):
    assert not await project_checks.inspect_helper(REFERENCES[check], check)


@pytest.mark.asyncio
@pytest.mark.parametrize('check,old,new', [
    ('video_seek_job', 'timer:null', 'timer:0'),
    ('video_seek_clear', 'job.timer!==null', 'job.timer'),
    ('video_seek_complete', 'clearSeekJob(job);job.resolve();', 'job.resolve();clearSeekJob(job);'),
    ('video_seek_fail', 'job.reject(error)', 'job.reject(new Error("Other error"))'),
    ('video_seek_arm', '5000', '500'),
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


@pytest.mark.asyncio
async def test_seek_jobs_compose_with_full_event_timeout_and_cleanup_cases():
    workers='\n'.join(REFERENCES[name] for name in (
        'video_seek_job','video_seek_clear','video_seek_complete','video_seek_fail','video_seek_arm'))
    wait='async function waitForVideoTime(video,target){if(Math.abs(video.currentTime-target)<.02)return;return new Promise((resolve,reject)=>{const job=makeSeekJob(video,resolve,reject);armSeekJob(job,target);});}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait,'video_export_wait')
    caller='async function seekExportStart(){return waitForVideoTime(ui.preview,app.start);}'
    assert not await project_checks.inspect_helper(workers+'\n'+wait+'\n'+caller,'video_export_seek')
    assert await project_checks.inspect_helper(workers.replace('clearTimeout(job.timer);','')+'\n'+wait,'video_export_wait')


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

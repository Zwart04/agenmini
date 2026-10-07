"""The coding skill assembles model source; it never supplies application code."""
import json
import hashlib
from pathlib import Path
import pytest
from app import project_parts, projects, llm, db, project_checks, project_patches


def test_missing_and_duplicate_model_slots_fail():
    with pytest.raises(ValueError, match='tepat satu'):
        project_parts.assemble('<!--panel:viewer--><!--panel:viewer-->', {'viewer':'model source'})
    with pytest.raises(ValueError, match='belum lengkap'):
        project_parts.assemble('<!--panel:viewer--><!--panel:library-->', {'viewer':'model source'})
    assert project_parts.assemble('before<!--panel:viewer-->after', {'viewer':'<section>model source</section>'}) == 'before<section>model source</section>after'


def test_recipe_is_instructions_not_runtime_source():
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text(encoding='utf-8'))
    assert all(project_parts.part_system(part['kind']) for part in recipe['parts'])
    assert all('source' not in part and 'task' in part for part in recipe['parts'])
    assert project_parts.supports('Build video editor with export')
    assert not project_parts.supports('Build video editor with export and database')
    assert not project_parts.supports('Build image converter with export')


def test_resume_requires_matching_model_source_and_task_hashes():
    item={'file':'app.js','task':'Write requested function'}
    source='model-authored source'
    saved={'source':source,'evidence':{'model':'test-model','sha256':hashlib.sha256(source.encode()).hexdigest(),
        'task_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}}
    assert project_parts.reusable_part(saved,item)['stats']=={'served_model':'test-model','reused':True}
    assert project_parts.reusable_part(saved,{**item,'task':'different requirement'}) is None
    assert project_parts.reusable_part({**saved,'source':'edited source'},item) is None


@pytest.mark.parametrize('patch',[
    {'edits':[{'find':'absent','replace':'new'}]},
    {'edits':[{'find':'same','replace':'new'}]},
    {'edits':[{'find':'same same','replace':'same same'}]},
    {'edits':[{'find':'same same','replace':''}]},
    {'edits':[{'find':'','replace':'new'}]},
    {'edits':[{'find':'same same','replace':'new','unexpected':True}]},
    {'edits':[{'find':'same same','replace':'first'},{'find':'absent','replace':'second'}]},
])
def test_model_patches_reject_ambiguous_noop_missing_empty_and_partial_edits(patch):
    with pytest.raises(ValueError):project_patches.apply('same same',json.dumps(patch))


def test_patch_cache_replays_model_bytes_and_rejects_modified_provenance():
    item={'file':'app.js','task':'Requested task'}
    origin='```js\nconst value = 1;\n```'
    raw=json.dumps({'edits':[{'find':'value = 1','replace':'value = 2'}]})
    source=project_patches.apply(projects.unwrap_file(origin,'app.js'),raw)
    chain=[{'base_sha256':project_patches.digest('const value = 1;'),
            'raw_patch':raw,'raw_sha256':project_patches.digest(raw),'source_sha256':project_patches.digest(source)}]
    saved={'source':source,'raw_source':raw,'origin_raw_source':origin,'repair_chain':chain,
           'evidence':{'sha256':project_patches.digest(source),'raw_sha256':project_patches.digest(raw),
                       'task_sha256':project_patches.digest(json.dumps(item,sort_keys=True,ensure_ascii=False))}}
    assert project_parts.reusable_part(saved,item)['patched_source']==source
    assert project_parts.reusable_part({**saved,'origin_raw_source':origin.replace('1','9')},item) is None
    assert project_parts.reusable_part({**saved,'repair_chain':[{**chain[0],'raw_patch':raw.replace('2','8')}]},item) is None


def test_patch_with_retained_correct_line_and_actual_change_is_not_a_noop():
    raw=json.dumps({'edits':[{'find':'keep();','replace':'keep();'},
                             {'find':'wrong();','replace':'fixed_by_model();'}]})
    assert project_patches.apply('keep();\nwrong();',raw)=='keep();\nfixed_by_model();'


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_model_patch_request_uses_selected_backend_and_supplies_no_runtime_template(monkeypatch,backend):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    async def chat(messages,**options):
        supplied=json.loads(messages[1]['content'])
        assert supplied['source']=='existing model bytes'
        assert supplied['errors']==['actual failure']
        if backend=='local':
            assert options['fmt']['type']=='json_schema'
            assert options['fmt']['json_schema']['schema']['properties']['edits']['items']['properties']['find']['enum']==['existing model bytes']
        else:assert options['fmt']=='json'
        return {'content':json.dumps({'edits':[{'find':'bytes','replace':'replacement from model'}]})}
    monkeypatch.setattr(llm,'chat',chat)
    result=await project_patches.request('existing model bytes',task='user task',errors=['actual failure'],contracts='actual contracts')
    assert project_patches.apply('existing model bytes',result['content'])=='existing model replacement from model'


def test_html_parts_receive_html_instructions_not_markdown():
    for kind in ('document','node','shell','shellchunk','panel'):
        instruction=project_parts.part_system(kind)
        assert 'HTML' in instruction and 'Markdown' not in instruction
    with pytest.raises(KeyError):project_parts.part_system('unknown-format')


def test_document_composition_preserves_model_bytes_without_creating_tags():
    shell='<html><body class="app"></body></html>'
    nodes={'header':'<header>model header</header>','stage':'<main class="stage"></main>','footer':'<footer>model footer</footer>'}
    panels={key:'<section>'+key+'</section>' for key in ('library','viewer','inspector','timeline')}
    output=project_parts.compose_document(shell,nodes,panels)
    assert output.count('<body')==1 and output.count('<main')==1
    assert output.index('library')<output.index('viewer')<output.index('inspector')<output.index('</main>')<output.index('timeline')
    with pytest.raises(ValueError):project_parts.compose_document(shell.replace('</body>','unrequested content</body>'),nodes,panels)


def test_select_model_node_preserves_exact_unicode_and_nested_source():
    node='<div class="viewer other">\n <div>你好 &amp; café</div>\n</div>'
    source='<html>\n<body>\n'+node+'<p>extraneous model text</p></body></html>'
    assert project_parts.extract_node(source,'viewer')==node
    with pytest.raises(ValueError):project_parts.extract_node(source,'missing')
    with pytest.raises(ValueError):project_parts.extract_node('<div class="viewer">unfinished','viewer')


def test_css_guard_rejects_instruction_prose_and_missing_colon():
    assert projects.inspect_css('.stage { grid-template-columns: 220px 1fr 250px gap:1px; }')
    assert projects.inspect_css('.viewer { flex-column; }')
    assert not projects.inspect_css('@media (max-width:700px) { .viewer {display:flex; flex-direction:column;} }')
    assert not projects.inspect_css('.hint {content:"https://example.com"; --custom: {x:y};}')


def test_document_cleanup_only_removes_unrequested_model_implementation():
    source='<html><head><style>model style</style><script defer src="app.js"></script></head><body class="app"><p>model extra</p><script>model code</script></body></html>'
    assert project_parts.document_container(source)=='<html><head><script defer src="app.js"></script></head><body class="app">\n</body></html>'
    with pytest.raises(ValueError):project_parts.document_container('<body>unfinished model source')


def test_sampling_profiles_are_copied_and_local_reasoning_defaults_off():
    first=llm.sampling_profile('qwen35-nonthinking');first['temperature']=99
    assert llm.sampling_profile('qwen35-nonthinking')['temperature']==1.0
    assert llm.sampling_profile('lfm25')['repetition_penalty']==1.05
    assert llm.coding_reasoning.get() is False


def test_contracts_reject_global_mobile_css_and_missing_dom_refs():
    item={'media_query':'(max-width:700px)'}
    assert project_parts.part_contract_errors('body {display:flex}',item)
    assert project_parts.part_contract_errors('@media (max-width:700px) {body{display:flex}} body{display:flex}',item)
    assert not project_parts.part_contract_errors('@media (max-width: 700px) {body{display:flex}}',item)
    assert project_parts.part_contract_errors("const ui={preview:document.getElementById('other')}",{'dom_refs':['preview']})
    assert not project_parts.part_contract_errors("const ui={preview:document.getElementById('preview')}",{'dom_refs':['preview']})


def test_js_context_keeps_contracts_without_previous_implementation():
    context=json.loads(project_parts.js_contract_context("const app={loaded:false}; const ui={preview:document.getElementById('preview')}; function loadVideo(file){ throw new Error('do not copy'); }"))
    assert context=={'globals':{'app':['loaded'],'ui':['preview']},'existing_functions':['function loadVideo(file)']}
    assert 'do not copy' not in str(context)
    assert json.loads(project_parts.js_contract_context('const app={"loaded":false};'))['globals']=={'app':['loaded']}
    assert not project_parts.part_contract_errors('const ui={"preview":document.getElementById("preview")}',{'dom_refs':['preview']})
    assert json.loads(project_parts.js_contract_context('const app={busy:false,loaded:false,canvas:null};',{'app':['busy','loaded']}))['globals']=={'app':['busy','loaded']}
    assert project_parts.part_contract_errors('function setBusy(flag){app.loaded=!flag}',{'state_writes':['busy']})
    assert not project_parts.part_contract_errors('function setBusy(flag){app.busy=Boolean(flag)}',{'state_writes':['busy']})


def test_js_rejects_invented_shared_state_and_browser_methods():
    prior="const app={loaded:false,ctx:null}; const ui={preview:null};"
    assert project_parts.js_shared_reference_errors('app.paused=true; app.audioContext.createMediaSource();',prior)
    assert project_parts.js_shared_reference_errors('ui.missing.play()',prior)
    assert not project_parts.js_shared_reference_errors('app.ctx.drawImage(ui.preview,0,0);',prior)


def test_function_contract_rejects_simulated_replacements_and_missing_startup():
    item={'functions':['initEditor'],'required_patterns':[r'\}\s*initEditor\(\s*\)\s*;?\s*$']}
    assert project_parts.part_contract_errors('function initEditor(){ /* Simulate loading video */ function loadVideo(){} }',item)
    assert project_parts.part_contract_errors('function initEditor(){}',item)
    assert not project_parts.part_contract_errors('function initEditor(){ui.playBtn.onclick=togglePlay;} initEditor();',item)
    assert not project_parts.part_contract_errors('function initEditor(){ui.titleInput.placeholder="Title";} initEditor();',item)


def test_css_contract_rejects_class_alias_for_actual_id():
    assert project_parts.part_contract_errors('.exportBtn{color:white}',{'css_selectors':['#exportBtn']})
    assert not project_parts.part_contract_errors('@media (max-width:700px){#exportBtn{color:white}}',{'css_selectors':['#exportBtn']})
    assert not project_parts.part_contract_errors('.library{padding:1px}.viewer{padding:1px}',{'css_selectors':['.library, .viewer']})


def test_fenced_source_with_explanation_is_selected_without_rewriting():
    source='body { color: #edf0f4; }'
    assert projects.unwrap_file('Here is the CSS:\n\n```css\n'+source+'\n```\nExplanation after it.','style.css')==source
    ambiguous='```css\nbody{color:red}\n```\n```css\nbody{color:blue}\n```'
    assert projects.unwrap_file(ambiguous,'style.css')==ambiguous
    assert projects.unwrap_file('```js\nconst a=1;\n```\n```css\n'+source+'\n```','style.css')==source


@pytest.mark.asyncio
async def test_helper_behavior_rejects_wrong_time_and_missing_shared_controls():
    assert await project_checks.inspect_helper('function formatTime(value){return "00:00"}', 'time_format')
    assert await project_checks.inspect_helper('function setBusy(flag){fileInput.disabled=flag}', 'busy')
    with pytest.raises(ValueError):await project_checks.inspect_helper('anything','untrusted-check')


@pytest.mark.asyncio
async def test_helper_behavior_detects_repeat_error_class_toggle():
    assert await project_checks.inspect_helper("function setStatus(message,isError=false){ui.status.textContent=message;if(isError)ui.status.classList.toggle('error');}", 'status')
    assert not await project_checks.inspect_helper("function setStatus(message,isError=false){ui.status.textContent=message;ui.status.classList.toggle('error',isError);}", 'status')
    assert not await project_checks.inspect_helper('function setStatus(message,isError=false){const node=document.querySelector("#status");node.textContent=message;if(isError)node.classList.add("error");else node.classList.remove("error");}', 'status')
    assert await project_checks.inspect_helper('function setStatus(message){document.querySelector(".status").textContent=message}', 'status')


@pytest.mark.asyncio
async def test_helper_behavior_bounds_execution_and_disallows_dynamic_code():
    assert await project_checks.inspect_helper('function formatTime(value){while(true){}}','time_format')
    assert await project_checks.inspect_helper('function formatTime(value){return Function("return process")()}','time_format')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_same_source_generation_path_for_all_backends(monkeypatch,backend):
    sentinel=object()
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    original=db.setting
    monkeypatch.setattr(db,'setting',lambda key,*a,**kw:'1' if key=='coding_parts_experimental' else original(key,*a,**kw))
    async def generate(brief,ctx,on_event=None):
        assert brief=='Build video editor with export'
        return sentinel
    monkeypatch.setattr(project_parts,'generate',generate)
    assert await projects.generate('Build video editor with export',object()) is sentinel

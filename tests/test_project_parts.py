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


def test_css_schema_constrains_structure_without_providing_declarations():
    import jsonschema
    item={'kind':'css','file':'style.css','css_selectors':['input[type="file"]']}
    schema=project_parts.css_source_schema(item)
    actual='input[type="file"] {padding: 11px; color: mintcream;}'
    jsonschema.validate({'source':actual},schema)
    assert 'padding' not in json.dumps(schema) and 'mintcream' not in json.dumps(schema)
    for invalid in ['.selector {color:red;}','input[type="file"]','input[type="file"] {color:red;']:
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':invalid},schema)
    assert project_parts.css_source_schema({**item,'media_query':'(max-width:700px)'}) is None
    assert project_parts.css_source_schema({**item,'kind':'js'}) is None


def test_html_schema_constrains_root_without_supplying_panel_implementation():
    import jsonschema
    item={'kind':'panel','root_class':'viewer'}
    schema=project_parts.html_source_schema(item)
    for source in ['<section class="viewer"><h2>Model title</h2></section>',"<div class='viewer extra'><p>Different model content</p></div>"]:
        jsonschema.validate({'source':source},schema)
    for source in ['<div class="viewer"></section>','<section class="viewer-surface"></section>','<!DOCTYPE html><section class="viewer"></section>']:
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':source},schema)
    assert 'video' not in json.dumps(schema) and 'playBtn' not in json.dumps(schema)
    assert project_parts.html_source_schema({**item,'kind':'js'}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_json_html_patch_reuses_decoded_root_with_exact_model_provenance(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Preview','file':'index.html','kind':'panel','task':'Model task','slot':'viewer','root_class':'viewer',
          'controls':{'preview':{'tag':'video'}},'absent_attributes':{'preview':['src']}}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':['viewer'],'required_ids':['preview']}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    original='<section class="viewer">\n<video id="preview" src=""></video>\n</section>'
    raw=json.dumps({'source':original})
    patch=json.dumps({'edits':[{'find':' src=""','replace':''}]})
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:
            assert 'ABSENT_ATTRIBUTES' in messages[1]['content']
            if backend=='local':assert options['fmt']['json_schema']['name']=='html_source'
            else:assert options['fmt']=='json'
            return {'content':raw,'stats':{'finish_reason':'stop','served_model':backend}}
        request=json.loads(messages[1]['content'])
        assert request['source']==original
        assert request['find_choices']==[' src=""']
        assert 'numbered_lines' not in request
        return {'content':patch,'stats':{'finish_reason':'stop','served_model':backend}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==project_patches.apply(original,patch)
            assert value['origin_raw_source']==raw
            assert value['evidence']['source_format']=='json_source'
            assert project_parts.reusable_part(value,item)['patched_source']==value['source']
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested application',object(),event)
    assert len(calls)==2


def test_forbidden_attribute_choices_preserve_unrelated_source_and_skip_ambiguous_spans():
    source='<video id="preview"\n SRC="bad > value" controls></video><video id="other" src="keep"></video>'
    errors=['preview must not have HTML attribute src.','preview must not have HTML attribute controls.']
    choices=project_patches.forbidden_attribute_choices(source,errors)
    assert choices==['\n SRC="bad > value"',' controls']
    patch=json.dumps({'edits':[{'find':span,'replace':''} for span in choices]})
    assert project_patches.apply(source,patch)=='<video id="preview"></video><video id="other" src="keep"></video>'
    ambiguous='<video id="preview" src=""></video><video id="other" src=""></video>'
    assert project_patches.forbidden_attribute_choices(ambiguous,errors)==[]
    assert project_patches.forbidden_attribute_choices(source,['Some unrelated failure'])==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_attribute_edit_rejects_unlisted_changes_on_every_backend(monkeypatch,backend):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='<video id="preview" src="" controls></video>'
    errors=['preview must not have HTML attribute src.','preview must not have HTML attribute controls.']
    async def model(messages,**options):
        request=json.loads(messages[1]['content'])
        assert request['find_choices']==[' src=""',' controls']
        if backend=='local':
            properties=options['fmt']['json_schema']['schema']['properties']['edits']['items']['properties']
            assert properties['replace']['const']==''
        return {'content':json.dumps({'edits':[{'find':' src=""','replace':' src="invented.mp4"'}]})}
    monkeypatch.setattr(llm,'chat',model)
    response=await project_patches.request(source,task='Keep the model video',errors=errors,contracts={},indexed=True)
    assert response['patch_validation_error']
    assert 'invented.mp4' in response['content']  # Preserve the failed response as evidence.


def test_nonvoid_self_closing_html_is_rejected_and_localized():
    item={'kind':'panel'}
    source='<section>\n<video id="preview" />\n<input id="seekInput" />\n</section>'
    errors=project_parts.part_contract_errors(source,item)
    assert errors==['preview must not use a self-closing HTML tag video; include explicit </video>.']
    assert project_patches.failing_lines(source,errors)==[2]
    assert project_parts.part_contract_errors('<section><video id="preview"></video><input /></section>',item)==[]


def test_fragment_checks_reject_real_nested_panel_and_mismatched_tag_failure():
    item={'kind':'panel','root_class':'timeline-panel','required_tags':['h2']}
    malformed='<section class="timeline-panel"><header class="timeline-panel"><main><aside><div id="timeline">Actual content</div></main></aside></section>'
    errors=project_parts.part_contract_errors(malformed,item)
    assert any(error.startswith('Fragment closing tag main') for error in errors)
    assert any(error.startswith('Root class timeline-panel') for error in errors)
    assert any('Required HTML tag h2' in error for error in errors)
    valid='<section class="timeline-panel"><h2>Timeline</h2><div id="timeline" class="timeline">Actual content</div></section>'
    assert project_parts.part_contract_errors(valid,item)==[]
    assert any('Duplicate HTML attributes' in error for error in project_parts.part_contract_errors(valid.replace('id="timeline"','id="timeline" role="region" role="alert"'),item))


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_model_selects_duplicate_attribute_removal_without_replacement_code(monkeypatch,backend):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='<section id="timeline">\r\n<div id="timeline">Actual model content</div>\r\n</section>'
    choices=project_patches.duplicate_id_choices(source,['Remove duplicate IDs.'])
    assert choices==[{'line':1,'remove':' id="timeline"'},{'line':2,'remove':' id="timeline"'}]
    async def model(messages,**options):
        request=json.loads(messages[1]['content'])
        assert request['removal_choices']==choices
        assert 'required control' in messages[0]['content']
        return {'content':json.dumps({'edits':[choices[0]]})}
    monkeypatch.setattr(llm,'chat',model)
    result=await project_patches.request(source,task='Keep timeline on inner div',errors=['Remove duplicate IDs.'],contracts={},indexed=True)
    assert not result.get('patch_validation_error')
    corrected=project_patches.apply(source,result['content'])
    assert corrected=='<section>\r\n<div id="timeline">Actual model content</div>\r\n</section>'
    chain=[{'base_sha256':project_patches.digest(source),'raw_patch':result['content'],
            'raw_sha256':project_patches.digest(result['content']),'source_sha256':project_patches.digest(corrected)}]
    assert project_patches.replay(source,chain,'index.html')==corrected
    for edits in ([choices[0],choices[0]],[{'line':9,'remove':' id="timeline"'}],[{'line':1,'remove':'not present'}]):
        with pytest.raises(ValueError):project_patches.apply(source,json.dumps({'edits':edits}))


def test_json_source_cache_replays_exact_decoded_model_bytes_and_patches():
    item={'file':'style.css','kind':'css','task':'model task','css_selectors':['.actual']}
    source='.actual {color: red;}'
    raw=json.dumps({'source':source})
    evidence={'task_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
              'sha256':project_patches.digest(source),'raw_sha256':project_patches.digest(raw),'source_format':'json_source'}
    saved={'source':source,'raw_source':raw,'evidence':evidence}
    assert project_parts.reusable_part(saved,item)['content']==raw
    assert project_parts.reusable_part({**saved,'source':'.actual {color: blue;}'},item) is None
    assert project_parts.reusable_part({**saved,'raw_source':json.dumps({'source':'.invented {}'})},item) is None
    patch=json.dumps({'edits':[{'line':1,'replace':'.actual {color: blue;}'}]})
    corrected=project_patches.apply(source,patch)
    chain=[{'base_sha256':project_patches.digest(source),'raw_sha256':project_patches.digest(patch),
            'raw_patch':patch,'source_sha256':project_patches.digest(corrected)}]
    saved={'source':corrected,'raw_source':patch,'origin_raw_source':raw,'repair_chain':chain,
           'evidence':{**evidence,'sha256':project_patches.digest(corrected),'raw_sha256':project_patches.digest(patch)}}
    reused=project_parts.reusable_part(saved,item)
    assert reused['patched_source']==corrected and reused['source_format']=='json_source'
    assert project_parts.reusable_part({**saved,'origin_raw_source':json.dumps({'source':'.invented {}'})},item) is None
    for invalid in ['broken',json.dumps({'source':source,'other':'hidden code'}),json.dumps({'source':5}),'{"source":"first","source":"second"}']:
        with pytest.raises(ValueError):project_parts.decode_source(invalid,'style.css','json_source')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_known_duplicate_declaration_is_repaired_by_model_and_rechecked(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Helper','file':'app.js','kind':'js','task':'Write helper','functions':['helper'],'include_html':False}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='function helper(value) {\nconst count = value;\nconst count = value + 1;\nreturn count;\n}'
    patch=json.dumps({'edits':[{'line':3,'replace':''}]})
    calls=[];events=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:return {'content':source,'stats':{'finish_reason':'stop','served_model':backend}}
        request=json.loads(messages[1]['content'])
        assert request['source']==source
        assert [line['line'] for line in request['numbered_lines']]==[2,3,4]
        assert any("Identifier 'count' has already been declared" in error for error in request['errors'])
        if backend=='local':assert options['fmt']['json_schema']['schema']['properties']['edits']['items']['properties']['line']['enum']==[2,3,4]
        else:assert options['fmt']=='json'
        return {'content':patch,'stats':{'finish_reason':'stop','served_model':backend}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        events.append((kind,value))
        if kind=='source_part':
            assert value['source']==project_patches.apply(source,patch)
            assert project_parts.reusable_part(value,{**item,'generation_contract_revision':2})['patched_source']==value['source']
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested application',object(),event)
    assert len(calls)==2
    checks=[value for kind,value in events if kind=='source_check']
    assert not checks[0]['passed'] and checks[1]['passed']


def test_duplicate_repair_does_not_allow_general_broken_source_or_missing_function():
    item={'kind':'js','functions':['helper']}
    errors=["SyntaxError: Identifier 'count' has already been declared"]
    assert project_parts.duplicate_declaration_repairable('function helper(){}',item,errors)
    assert not project_parts.duplicate_declaration_repairable('helper(){}',item,errors)
    assert not project_parts.duplicate_declaration_repairable('function helper(){}',item,['SyntaxError: Unexpected end of input'])
    assert not project_parts.duplicate_declaration_repairable('function helper(){}',{**item,'kind':'css'},errors)


def test_css_semantic_contract_rejects_actual_layout_drift_and_hidden_priority():
    item={'kind':'css','css_selectors':['.viewer'],'css_declarations':{'display':'flex','min-width':'0'}}
    assert project_parts.part_contract_errors('.viewer{display:grid;min-width:0}',item)
    assert project_parts.part_contract_errors('.viewer{display:flex;min-width:0;background:white}',item)
    assert not project_parts.part_contract_errors('.viewer{display:flex; min-width: /* prevent overflow */ 0;}',item)
    assert project_parts.part_contract_errors('.viewer{display:grid!important;display:flex;min-width:0}',item)
    hidden={'kind':'css','css_selectors':['[hidden]'],'css_declarations':{'display':'none !important'}}
    assert project_parts.part_contract_errors('[hidden]{display:none}',hidden)
    assert not project_parts.part_contract_errors('[hidden]{display:none!important}',hidden)
    assert not project_parts.part_contract_errors('@media(max-width:700px){.viewer{display:flex;min-width:0}}',item)


def test_viewer_contract_rejects_nested_transport_and_empty_media_src():
    item={'kind':'panel','direct_parent_classes':{'#preview':'viewer-surface','.transport':'viewer','#playBtn':'transport'},'absent_attributes':{'preview':['src','controls']}}
    invalid='<section class="viewer"><div class="viewer-surface"><video id="preview" src=""></video><div class="transport"><button id="playBtn">Play</button></div></div></section>'
    errors=project_parts.part_contract_errors(invalid,item)
    assert any('.transport must be a direct child' in error for error in errors)
    assert any('must not have HTML attribute src' in error for error in errors)
    valid='<section class="viewer"><div class="viewer-surface"><video id="preview"></video></div><div class="transport"><input type="range"><button id="playBtn">Play</button></div></section>'
    assert not project_parts.part_contract_errors(valid,item)
    assert not project_parts.part_contract_errors(valid.replace('<input type="range">','<input type="range"/>'),item)


@pytest.mark.asyncio
async def test_helper_feedback_includes_actual_values_without_splitting_source_strings():
    errors=await project_checks.inspect_helper('function formatTime(value){return "wrong; value"}', 'time_format')
    assert errors and len(errors)==12
    assert all(' [observed "wrong; value"]' in error for error in errors)
    assert all(error.startswith('Helper behavior failed: formatTime(') for error in errors)
    assert any('formatTime(65.9)' in error for error in errors)
    assert any('formatTime(3599)' in error for error in errors)
    assert project_parts.helper_failure_identity(errors[0])==project_parts.helper_failure_identity(errors[0].replace('wrong; value','different wrong result'))
    assert project_parts.helper_failure_identity(errors[0])!=project_parts.helper_failure_identity(errors[1])


@pytest.mark.asyncio
async def test_truncated_diagnosis_is_retained_but_not_sent_as_patch_plan(monkeypatch):
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:return {'content':'An incomplete model analysis','stats':{'finish_reason':'length','served_model':'selected-model'}}
        assert 'repair_plan' not in json.loads(messages[1]['content'])
        return {'content':json.dumps({'edits':[{'find':'wrong','replace':'model correction'}]})}
    monkeypatch.setattr(llm,'chat',model)
    result=await project_patches.request('wrong',task='actual task',errors=['actual error'],contracts='',diagnose=True)
    assert result['repair_plan']['text']=='An incomplete model analysis'
    assert result['repair_plan']['finish_reason']=='length'
    assert project_patches.apply('wrong',result['content'])=='model correction'


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


def test_html_patch_replay_preserves_selected_model_node_and_discards_no_new_source():
    node='<header class="topbar"><button id="cancelBtn">Cancel</button></header>'
    origin='<html><body>'+node+'</body></html>'
    raw=json.dumps({'edits':[{'find':'id="cancelBtn"','replace':'id="cancelBtn" hidden'}]})
    source=project_patches.apply(node,raw)
    chain=[{'base_sha256':project_patches.digest(node),'raw_patch':raw,
            'raw_sha256':project_patches.digest(raw),'source_sha256':project_patches.digest(source)}]
    item={'file':'index.html','task':'model task','root_class':'topbar'}
    saved={'source':source,'raw_source':raw,'origin_raw_source':origin,'repair_chain':chain,
           'evidence':{'sha256':project_patches.digest(source),'raw_sha256':project_patches.digest(raw),
                       'task_sha256':project_patches.digest(json.dumps(item,sort_keys=True,ensure_ascii=False))}}
    assert project_parts.reusable_part(saved,item)['patched_source']==source
    assert project_parts.reusable_part(saved,{**item,'root_class':'missing'}) is None


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


@pytest.mark.asyncio
async def test_invalid_syntax_patch_is_rolled_back_before_next_model_repair(monkeypatch,tmp_path):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Style','file':'style.css','kind':'css','task':'model task','css_selectors':['.correct']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:'local')
    original='.wrong {color:red;}'
    responses=[json.dumps({'source':original}),json.dumps({'edits':[{'line':1,'replace':'.correct {color:red;'}]}),json.dumps({'source':'.correct {color:red;}'})]
    calls=[];events=[]
    async def model(messages,**options):
        if len(calls)>=2:
            assert options['fmt']['json_schema']['name']=='css_source'
            assert 'Original source restored' in messages[1]['content']
            assert 'EOF reached' not in messages[1]['content']
            assert original not in messages[1]['content']
        if len(calls)==1:
            assert 'Output raw source only' not in json.loads(messages[1]['content'])['contracts']
        calls.append(messages)
        return {'content':responses[len(calls)-1],'stats':{'finish_reason':'stop','served_model':'fixture-model'}}
    monkeypatch.setattr(llm,'chat',model)
    class ReachedValidatedSource(Exception):pass
    async def event(kind,value):
        events.append((kind,value))
        if kind=='source_part':raise ReachedValidatedSource()
    with pytest.raises(ReachedValidatedSource):await project_parts.generate('requested application',object(),event)
    accepted=next(value for kind,value in events if kind=='source_part')
    assert accepted['source']=='.correct {color:red;}'
    assert not accepted.get('repair_chain')
    rejected=next(value for kind,value in events if kind=='source_check' and value['attempt']==1)
    assert not rejected['passed']
    assert any(kind=='code' and value.get('restored') for kind,value in events)


@pytest.mark.asyncio
async def test_repair_diagnosis_is_model_authored_and_never_applied_as_source(monkeypatch):
    original='existing source'
    async def model(messages,**options):
        supplied=json.loads(messages[1]['content'])
        assert supplied['source']==original
        if 'fmt' not in options:return {'content':'Explain the actual error and replace only the failing text.','stats':{'served_model':'selected-model'}}
        assert supplied['repair_plan']=='Explain the actual error and replace only the failing text.'
        return {'content':json.dumps({'edits':[{'find':'existing','replace':'repaired'}]}),'stats':{'served_model':'selected-model'}}
    monkeypatch.setattr(llm,'chat',model)
    result=await project_patches.request(original,task='actual task',errors=['actual failure'],contracts='actual contracts',diagnose=True)
    assert project_patches.apply(original,result['content'])=='repaired source'
    assert result['repair_plan']['model']=='selected-model'


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
@pytest.mark.parametrize('reasoning',[False,True])
async def test_patch_and_diagnosis_reserve_answer_tokens_for_bounded_local_reasoning(monkeypatch,backend,reasoning):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    token=llm.coding_reasoning.set(reasoning);limits=[]
    async def model(messages,**options):
        limits.append(options['max_tokens'])
        return {'content':'model diagnosis' if len(limits)==1 else json.dumps({'edits':[{'line':1,'replace':'model correction'}]}),'stats':{'served_model':backend}}
    monkeypatch.setattr(llm,'chat',model)
    try:
        result=await project_patches.request('original',task='actual task',errors=['actual failure'],contracts='actual contracts',diagnose=True,indexed=True,max_tokens=450)
        extra=512 if backend=='local' and reasoning else 0
        assert limits==[220+extra,450+extra]
        assert result['repair_plan']['text']=='model diagnosis'
    finally:llm.coding_reasoning.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_incomplete_source_is_regenerated_by_selected_model_instead_of_patched(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Visibility','file':'style.css','kind':'css','task':'Write the required visibility rule','css_selectors':['[hidden]']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if backend=='local':assert options['fmt']['json_schema']['name']=='css_source'
        else:assert options['fmt']=='json'
        assert 'Required selectors are literal CSS selectors' in messages[0]['content']
        assert '[hidden]' in messages[0]['content']
        if len(calls)==1:assert 'REQUIRED_SELECTORS' in messages[1]['content']
        if len(calls)==1:return {'content':json.dumps({'source':'[hidden]:'}),'stats':{'finish_reason':'stop'}}
        assert '[hidden]:' not in messages[1]['content'] and 'CHECK ERRORS' in messages[1]['content']
        return {'content':json.dumps({'source':'[hidden] {display:none!important;}'}),'stats':{'finish_reason':'stop','served_model':backend}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']=='[hidden] {display:none!important;}'
            assert json.loads(value['raw_source'])['source']==value['source']
            assert not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested application',object(),event)
    assert len(calls)==2


def test_cached_patch_rejects_tampered_model_diagnosis():
    original='model source'
    raw=json.dumps({'edits':[{'find':'source','replace':'repair'}]})
    chain=[{'base_sha256':project_patches.digest(original),'raw_patch':raw,
            'raw_sha256':project_patches.digest(raw),'source_sha256':project_patches.digest('model repair'),
            'repair_plan':{'text':'actual diagnosis','sha256':project_patches.digest('actual diagnosis')}}]
    assert project_patches.replay(original,chain,'app.js')=='model repair'
    chain[0]['repair_plan']['text']='changed diagnosis'
    with pytest.raises(ValueError,match='diagnosis changed'):project_patches.replay(original,chain,'app.js')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
@pytest.mark.parametrize('invalid_source',[
    '<aside class="library"><label for="fileInput">Import</label></aside>',
    '<aside class="library"><div id="fileInput" type="file">Import</div></aside>',
])
async def test_missing_import_element_is_regenerated_instead_of_copying_incomplete_panel(monkeypatch,tmp_path,backend,invalid_source):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Library','file':'index.html','kind':'panel','task':'Include a real video file input','slot':'library','root_class':'library','controls':{'fileInput':{'tag':'input','type':'file'}}}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':['library'],'required_ids':['fileInput']}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    calls=[]
    complete='<aside class="library"><label for="fileInput">Import</label><input id="fileInput" type="file"></aside>'
    async def model(messages,**options):
        calls.append(messages)
        if backend=='local':assert options['fmt']['json_schema']['name']=='html_source'
        else:assert options['fmt']=='json'
        if len(calls)==1:return {'content':json.dumps({'source':invalid_source}),'stats':{'finish_reason':'stop'}}
        assert 'Required control fileInput' in messages[1]['content']
        assert '<aside' not in messages[1]['content']
        return {'content':json.dumps({'source':complete}),'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==complete and not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested video editor',object(),event)
    assert len(calls)==2


def test_indexed_patch_addresses_original_lines_atomically_and_preserves_endings():
    source='same\r\nsame\r\nlast'
    raw=json.dumps({'edits':[{'line':1,'replace':'first\nextra'},{'line':2,'replace':'second'},{'line':3,'replace':'end'}]})
    assert project_patches.apply(source,raw)=='first\nextra\r\nsecond\r\nend'
    for edits in ([{'line':2,'replace':'valid'},{'line':8,'replace':'missing'}],
                  [{'line':1,'replace':'a'},{'line':1,'replace':'b'}],
                  [{'line':True,'replace':'bad'}],
                  [{'line':1,'replace':'a'},{'find':'same','replace':'b'}]):
        with pytest.raises(ValueError):project_patches.apply(source,json.dumps({'edits':edits}))
    with pytest.raises(ValueError):project_patches.apply('a',json.dumps({'edits':[{'line':1,'replace':''}]}))
    with pytest.raises(ValueError):project_patches.apply('a',json.dumps({'edits':[{'line':1,'replace':'a'}]}))


def test_failing_line_selection_uses_check_identifiers_and_falls_back_for_unknown_errors():
    source='function f(){\n ui.playBtn.disabled=flag;\n ui.playBtnExtra.disabled=flag;\n ui.seekInput.disabled=flag;\n}'
    assert project_patches.failing_lines(source,['playBtn.disabled expected true; seekInput.disabled expected true'])==[2,4]
    assert project_patches.failing_lines(source,['Unexpected end of input'])==[1,2,3,4,5]
    assert project_patches.failing_lines(source,['playBtn.disabled expected true','Missing helper declaration'])==[1,2,3,4,5]
    html='<header>\n<button id="cancelBtn">Cancel</button>\n</header>'
    assert project_patches.failing_lines(html,['cancelBtn must have HTML attribute hidden.'])==[2]
    assert project_patches.failing_lines('.wrong {\n color:red;\n}', ['Missing CSS selector .correct; preserve punctuation.'])==[1]
    assert project_patches.failing_lines('@media (max-width:700px){\n.wrong {color:red}\n}', ['Missing CSS selector .correct; preserve punctuation.'])==[2]


@pytest.mark.asyncio
async def test_model_repair_cannot_fix_playback_by_breaking_initial_import(monkeypatch,tmp_path):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Busy','file':'app.js','kind':'js','task':'Control loading state','functions':['setBusy'],'behavior_checks':['busy']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:'local')
    def fixture_source(import_logic,playback_logic):
        return 'function setBusy(flag){app.busy=flag;ui.fileInput.disabled='+import_logic+';'+''.join('ui.'+ident+'.disabled='+playback_logic+';' for ident in ('playBtn','seekInput','startInput','endInput','exportBtn'))+'ui.cancelBtn.hidden=!flag;}'
    original=fixture_source('flag','flag')
    broken=fixture_source('flag||!app.loaded','flag||!app.loaded')
    corrected=fixture_source('flag','flag||!app.loaded')
    responses=[original,json.dumps({'edits':[{'line':1,'replace':broken}]}),corrected]
    calls=[];events=[]
    async def model(messages,**options):
        if len(calls)>=2:
            assert 'fmt' not in options
            assert original not in messages[1]['content'] and broken not in messages[1]['content']
            assert 'new failing behavior cases' in messages[1]['content']
        calls.append(messages)
        return {'content':responses[len(calls)-1],'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        events.append((kind,value))
        if kind=='source_part':
            assert value['source']==corrected and not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested video editor',object(),event)
    rejected=next(value for kind,value in events if kind=='source_check' and value['attempt']==1)
    assert any('fileInput.disabled' in error for error in rejected['errors'])
    assert any(kind=='code' and value.get('restored') for kind,value in events)


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_indexed_repair_can_change_five_controls_without_copying_function(monkeypatch,backend):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='\n'.join('control'+str(i)+'.disabled = busy;' for i in range(5))
    async def model(messages,**options):
        supplied=json.loads(messages[1]['content'])
        assert supplied['numbered_lines']==[{'line':i+1,'text':line} for i,line in enumerate(source.splitlines())]
        assert 'find_choices' not in supplied
        if backend=='local':
            fields=options['fmt']['json_schema']['schema']['properties']['edits']['items']['properties']
            assert fields['line']['enum']==[1,2,3,4,5]
            assert fields['replace']['pattern']=='^[^\r\n]*$'
        else:assert options['fmt']=='json'
        return {'content':json.dumps({'edits':[{'line':i+1,'replace':'control'+str(i)+'.disabled = busy || !loaded;'} for i in range(5)]})}
    monkeypatch.setattr(llm,'chat',model)
    result=await project_patches.request(source,task='actual control logic',errors=['unloaded controls enabled'],contracts='actual field declarations',indexed=True)
    repaired=project_patches.apply(source,result['content'])
    chain=[{'base_sha256':project_patches.digest(source),'raw_patch':result['content'],
            'raw_sha256':project_patches.digest(result['content']),'source_sha256':project_patches.digest(repaired)}]
    assert project_patches.replay(source,chain,'app.js')==repaired
    assert repaired.count('busy || !loaded')==5


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
    assert llm.sampling_profile('greedy')=={'temperature':0.0}
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


def test_requested_system_font_does_not_accept_unknown_multiword_family():
    item={'css_selectors':['body'],'css_generic_font':True}
    assert project_parts.part_contract_errors('body{font:13px system-ui sans-serif;}',item)
    assert project_parts.part_contract_errors('body{font-size:13px;font-family:system-ui sans-serif;}',item)
    assert project_parts.part_contract_errors('body{font-family:"system-ui";} .other{font-family:sans-serif}',item)
    assert not project_parts.part_contract_errors('body{font-size:13px;font-family:system-ui,sans-serif;}',item)
    assert not project_parts.part_contract_errors('body{font-family:"Segoe UI", /* fallback */ sans-serif;}',item)


def test_html_visibility_contract_rejects_inline_display_that_hidden_cannot_toggle():
    item={'kind':'node','present_attributes':{'downloadLink':['hidden','download']},
          'absent_attributes':{'downloadLink':['href']},'required_tags':['h1']}
    assert project_parts.part_contract_errors('<h1>Editor</h1><a id="downloadLink" style="display:none">Download</a>',item)
    assert project_parts.part_contract_errors('<h1>Editor</h1><a id="downloadLink" hidden download href="#">Download</a>',item)
    assert not project_parts.part_contract_errors('<h1>Editor</h1><a id="downloadLink" hidden download>Download</a>',item)
    assert project_parts.part_contract_errors('<h1>Editor</h1><a id="downloadLink" hidden download onclick="undeclaredHelper()">Download</a>',item)


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

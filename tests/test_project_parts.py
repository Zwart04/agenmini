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
    mobile_schema=project_parts.css_source_schema({**item,'media_query':'(max-width:700px)'})
    jsonschema.validate({'source':'@media (max-width:700px) {input[type="file"] {padding: 11px;}}'},mobile_schema)
    for invalid in ['input[type="file"] {padding:11px;}', '@media (max-width:700px) {["input[type=file]"] {padding:11px;}}', '@media (max-width:600px) {input[type="file"] {padding:11px;}}']:
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':invalid},mobile_schema)
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
    exact={**item,'root_tag':'section'}
    exact_schema=project_parts.html_source_schema(exact)
    jsonschema.validate({'source':'<section class="viewer"><p>Model content</p></section>'},exact_schema)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':'<aside class="viewer"></aside>'},exact_schema)
    assert 'aside' not in json.dumps(exact_schema)
    assert project_parts.part_contract_errors('<aside class="viewer"></aside>',exact)==['Root class viewer must use tag section.']


def test_javascript_schema_constrains_function_without_supplying_logic():
    import jsonschema
    schema=project_parts.js_source_schema({'kind':'js','functions':['modelHelper']})
    jsonschema.validate({'source':'function modelHelper(input) { return input * 17; }'},schema)
    jsonschema.validate({'source':'async function modelHelper(input) { return await input; }'},schema)
    assert 'return' not in json.dumps(schema) and '17' not in json.dumps(schema)
    for source in ['import { modelHelper } from "./app.js";','function wrongName(input) {return input;}','const modelHelper = input => input;']:
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':source},schema)
    assert project_parts.js_source_schema({'kind':'js','functions':['first','second']}) is None
    assert project_parts.js_source_schema({'kind':'css','functions':['modelHelper']}) is None


def test_repair_prompt_examples_do_not_discard_any_validation_results():
    errors=[f'Helper behavior failed: actual case {index}' for index in range(12)]+['Actual syntax error']
    assert project_patches.prompt_errors(errors)==errors[:3]+errors[-1:]
    assert len(errors)==13


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
            assert '"pattern"' not in messages[0]['content']
            if backend=='local':
                assert options['fmt']['json_schema']['name']=='html_source'
                assert options['fmt']['json_schema']['schema']==project_parts.source_response_schema()
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


def test_required_element_text_cannot_be_satisfied_by_attributes_or_other_elements():
    item={'kind':'panel','required_text':{'timeline':'Import a clip to begin editing'}}
    invalid='<h2>Import a clip to begin editing</h2><div id="timeline" initial text="Import a clip to begin editing"></div>'
    assert any('not text in attributes' in error for error in project_parts.part_contract_errors(invalid,item))
    assert project_parts.part_contract_errors('<div id="timeline">Import a clip <span>to begin editing.</span></div>',item)==[]
    assert project_parts.part_contract_errors('<div id="timeline">Import\n a clip to begin editing.</div>',item)==[]


def test_empty_model_container_is_filled_without_new_markup():
    wrapper='<section class="timeline-panel">\n</section>'
    heading='<h2 class="timeline-heading">Model heading</h2>'
    track='<div id="timeline">Actual model content</div>'
    combined=project_parts.fill_model_container(wrapper,[heading,track])
    assert combined=='<section class="timeline-panel">\n'+heading+'\n'+track+'\n</section>'
    for invalid in ['<section></div>','<section>Unrequested model body</section>']:
        with pytest.raises(ValueError):project_parts.fill_model_container(invalid,[track])
    item={'kind':'node','root_class':'timeline-panel','empty_container':True}
    assert project_parts.part_contract_errors(wrapper,item)==[]
    assert any('empty container' in e for e in project_parts.part_contract_errors(combined,item))
    restricted={**item,'root_tag':'section','root_only_class':True}
    assert any('only the class attribute' in e for e in project_parts.part_contract_errors(wrapper.replace('class="timeline-panel"','class="timeline-panel" id="timeline"'),restricted))
    import jsonschema
    schema=project_parts.html_source_schema(restricted)
    jsonschema.validate({'source':wrapper},schema)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate({'source':combined},schema)


def test_model_heading_is_selected_verbatim_and_validated_as_a_real_element():
    source='<h2 class="timeline-heading">Timeline</h2>'
    assert project_parts.extract_node(source,'timeline-heading')==source
    assert project_parts.extract_node('Prefix\n'+source+'\nUnrequested suffix','timeline-heading')==source
    with pytest.raises(ValueError):project_parts.extract_node(source.replace('</h2>',''),'timeline-heading')


@pytest.mark.asyncio
async def test_reordered_recipe_reuses_only_identical_verified_model_task(monkeypatch,tmp_path):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Rule','file':'style.css','kind':'css','task':'Write the actual selector','css_selectors':['.actual']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    source='.actual {color: red;}'
    saved={'source':source,'raw_source':source,'evidence':{'model':'original-model','sha256':project_patches.digest(source),'raw_sha256':project_patches.digest(source),'task_sha256':project_patches.digest(json.dumps(item,sort_keys=True,ensure_ascii=False))}}
    token=project_parts.part_cache.set({41:saved,0:{**saved,'source':'.wrong {color: blue;}'}})
    async def model(*args,**kwargs):raise AssertionError('A verified identical model task should be reused.')
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==source and value['evidence']['reused']
            assert value['evidence']['model']=='original-model'
            raise Validated()
    try:
        with pytest.raises(Validated):await project_parts.generate('requested application',object(),event)
    finally:project_parts.part_cache.reset(token)


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
        if len(calls)==1:
            if backend=='local':assert options['fmt']['json_schema']['name']=='js_source'
            else:assert options['fmt']=='json'
            return {'content':json.dumps({'source':source}),'stats':{'finish_reason':'stop','served_model':backend}}
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
    source_missing='function clock(total){\n const minutes=Math.floor(total/60);\n const seconds=total%60;\n const m=padStart(minutes,2,"0");\n const s=padStart(seconds,2,"0");\n return m+":"+s;\n}'
    assert project_patches.failing_lines(source_missing,['Helper behavior failed: padStart is not defined'])==[4,5]
    assert project_patches.failing_lines(source_missing,['ReferenceError: padStart is not defined'])==[4,5]
    assert project_patches.failing_lines(source_missing,['Helper behavior failed: padStart is not defined','Missing behavior'])==list(range(1,8))
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
    responses=[json.dumps({'source':original}),json.dumps({'edits':[{'line':1,'replace':broken}]}),json.dumps({'source':corrected})]
    calls=[];events=[]
    async def model(messages,**options):
        if len(calls)>=2:
            assert options['fmt']['json_schema']['name']=='js_source'
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
            assert 'pattern' not in fields['replace']
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
    prior='function normalizeSeconds(value){return 0;} async function unrelated(file){throw "secret implementation";}'
    assert json.loads(project_parts.js_contract_context(prior,functions=[]))['existing_functions']==[]
    assert json.loads(project_parts.js_contract_context(prior,functions=['normalizeSeconds']))['existing_functions']==['function normalizeSeconds(value)']
    assert json.loads(project_parts.js_contract_context('const app={"loaded":false};'))['globals']=={'app':['loaded']}
    assert not project_parts.part_contract_errors('const ui={"preview":document.getElementById("preview")}',{'dom_refs':['preview']})
    assert json.loads(project_parts.js_contract_context('const app={busy:false,loaded:false,canvas:null};',{'app':['busy','loaded']}))['globals']=={'app':['busy','loaded']}
    assert project_parts.part_contract_errors('function setBusy(flag){app.loaded=!flag}',{'state_writes':['busy']})
    assert not project_parts.part_contract_errors('function setBusy(flag){app.busy=Boolean(flag)}',{'state_writes':['busy']})


def test_js_rejects_invented_shared_state_and_browser_methods():
    assert project_parts.part_contract_errors('function f(){return 1;} function f(){return 2;}',{'functions':['f']})==['Duplicate requested function declaration: f']
    assert not project_parts.part_contract_errors('function f(){return 1;} function g(){return 2;}',{'functions':['f','g']})
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
async def test_decomposed_time_helpers_reject_coercion_and_wrong_arithmetic():
    normalize='function normalizeSeconds(value){return Number.isFinite(value)&&value>=0?Math.floor(value):0;}'
    clock='function secondsToClock(total){return String(Math.floor(total/60)).padStart(2,"0")+":"+String(total%60).padStart(2,"0");}'
    formatter='function formatTime(value){return secondsToClock(normalizeSeconds(value));}'
    assert not await project_checks.inspect_helper(normalize,'normalize_seconds')
    assert await project_checks.inspect_helper('function normalizeSeconds(value){return Math.floor(Number(value))||0;}','normalize_seconds')
    assert not await project_checks.inspect_helper(clock,'seconds_clock')
    assert await project_checks.inspect_helper('function secondsToClock(total){return "00:"+total;}','seconds_clock')
    assert not await project_checks.inspect_helper(normalize+'\n'+clock+'\n'+formatter,'time_format')
    assert await project_checks.inspect_helper(formatter,'time_format')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_behavior_dependencies_use_only_accepted_model_functions(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    sources=['const app={loaded:false}; const ui={};',
             'function normalizeSeconds(value){return Number.isFinite(value)&&value>=0?Math.floor(value):0;}',
             'function secondsToClock(total){return String(Math.floor(total/60)).padStart(2,"0")+":"+String(total%60).padStart(2,"0");}',
             'function formatTime(value){return secondsToClock(normalizeSeconds(value));}']
    parts=[{'name':'Globals','file':'app.js','kind':'js','task':'Define state'},
           *[{'name':fn,'file':'app.js','kind':'js','task':'Write '+fn,'functions':[fn]} for fn in ('normalizeSeconds','secondsToClock')],
           {'name':'Formatter','file':'app.js','kind':'js','task':'Compose helpers','functions':['formatTime'],
            'behavior_dependencies':['normalizeSeconds','secondsToClock'],'behavior_checks':['time_format']}]
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':parts,'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    calls=[]
    async def model(messages,**options):
        source=sources[len(calls)];calls.append(messages)
        return {'content':source if len(calls)==1 else json.dumps({'source':source}),'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part' and value['index']==3:
            assert value['source']==sources[3]
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested editor',object(),event)
    assert len(calls)==4


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_duplicate_model_function_is_regenerated_before_assembly(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Helper','file':'app.js','kind':'js','task':'Write one function helper','functions':['helper']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    calls=[];good='function helper(value){return value;}'
    async def model(messages,**options):
        if calls:
            assert 'Duplicate requested function declaration' in messages[1]['content']
            if backend=='local':assert options['fmt']['json_schema']['name']=='js_source'
            else:assert options['fmt']=='json'
        calls.append(messages)
        source='function helper(){return "old";} function helper(){return "overridden";}' if len(calls)==1 else good
        return {'content':json.dumps({'source':source}),'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==good and not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested editor',object(),event)
    assert len(calls)==2


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


def test_repeated_function_selection_preserves_exact_model_bytes_and_rejects_ambiguity():
    item={'kind':'js','functions':['clock']}
    unit='function clock(total) {\r\n  return String(total);\r\n}'
    assert project_parts.select_repeated_function('\n'+unit+'\n\n'+unit+'\n'+unit+'\n',item)==unit
    for response in (unit+'\n'+unit.replace('String(total)','total'),
                     unit+'\nfunction other(){return 0;}\n'+unit,
                     unit+'\n'+unit+'\nclock(5);',
                     'const secret=1;\n'+unit+'\n'+unit):
        assert project_parts.select_repeated_function(response,item)==response
    assert project_parts.select_repeated_function(unit+'\n'+unit,{'kind':'js','functions':['clock','other']})==unit+'\n'+unit


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_identical_model_function_repetition_selects_one_span_with_replayable_provenance(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Status','file':'app.js','kind':'js','task':'Write status helper','functions':['setStatus'],'behavior_checks':['status']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='function setStatus(message,isError=false){ui.status.textContent=message;ui.status.classList.toggle("error",isError);}'
    raw=json.dumps({'source':source+'\n\n'+source+'\n'+source})
    async def model(messages,**options):return {'content':raw,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==source and value['raw_source']==raw
            assert value['evidence']['initial_selection']=='one exact parsed model-written helper span'
            assert project_parts.reusable_part(value,{**item,'generation_contract_revision':2})['content']==raw
            assert project_parts.reusable_part({**value,'source':source.replace('message','changed')},{**item,'generation_contract_revision':2}) is None
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested editor',object(),event)


def test_source_response_schema_keeps_json_strings_without_unsafe_code_patterns():
    import jsonschema
    schema=project_parts.source_response_schema()
    source='function f(){\n const text="kutip \\\" dan 日本語";\n return text;\n}'
    jsonschema.validate({'source':source},schema)
    assert project_parts.decode_source(json.dumps({'source':source}),'app.js','json_source')==source
    for invalid in ({'source':source,'type':'object'},{'source':None},{'source':{}},{}):
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate(invalid,schema)
    assert 'pattern' not in schema['properties']['source']


def test_repeated_function_selection_replays_model_patches_and_rejects_changed_origin():
    item={'kind':'js','file':'app.js','functions':['f'],'task':'model task'}
    unit='function f(){return 1;}'
    corrected='function f(){return 2;}'
    origin=json.dumps({'source':unit+'\n'+unit})
    patch=json.dumps({'edits':[{'line':1,'replace':corrected}]})
    chain=[{'base_sha256':project_patches.digest(unit),'raw_patch':patch,
            'raw_sha256':project_patches.digest(patch),'source_sha256':project_patches.digest(corrected)}]
    evidence={'task_sha256':project_patches.digest(json.dumps(item,sort_keys=True,ensure_ascii=False)),
              'sha256':project_patches.digest(corrected),'raw_sha256':project_patches.digest(patch),'source_format':'json_source'}
    saved={'source':corrected,'raw_source':patch,'origin_raw_source':origin,'repair_chain':chain,'evidence':evidence}
    assert project_parts.reusable_part(saved,item)['patched_source']==corrected
    changed=json.dumps({'source':unit+'\n'+corrected})
    assert project_parts.reusable_part({**saved,'origin_raw_source':changed},item) is None
    assert project_parts.reusable_part({**saved,'source':unit},item) is None


def test_parsed_helper_selection_does_not_execute_source_and_preserves_unicode_spans(tmp_path):
    item={'kind':'js','functions':['target'],'behavior_checks':['status']}
    marker=tmp_path/'must-not-exist'
    prefix='require("node:fs").writeFileSync('+json.dumps(str(marker))+',"executed");\nconst emoji="🎬";\n'
    target='function target(value){const text="{}🎬";return `${value}:${text}`;}'
    source=prefix+'function unrelated(){return 0;}\n'+target+'\nconsole.log("unsolicited example");'
    assert project_parts.select_model_helper(source,item)==target
    assert not marker.exists()
    with pytest.raises(ValueError,match='Multiple different'):
        project_parts.select_model_helper(target+'\n'+target.replace('return `${value}:${text}`','return "changed"'),item)
    broken='function target(value){return'
    assert project_parts.select_model_helper(broken,item)==broken


@pytest.mark.asyncio
async def test_selected_model_helper_still_fails_actual_behavior_check():
    item={'kind':'js','functions':['formatTime'],'behavior_checks':['time_format']}
    source='function fake(){return 9;} function formatTime(value){return "00:00";}'
    selected=project_parts.select_model_helper(source,item)
    assert selected=='function formatTime(value){return "00:00";}'
    assert await project_checks.inspect_helper(selected,'time_format')


def test_js_contracts_preserve_outer_fields_after_nested_objects_and_ignore_locals():
    source='const app={globals:{hidden:1},loaded:false,busy:false,note:"}🎬",nested:{deep:{field:1}}};const ui={preview:document.getElementById("preview")};function f(){const app={fake:1};return 0;}'
    context=json.loads(project_parts.js_contract_context(source))
    assert context['globals']=={'app':['globals','loaded','busy','note','nested'],'ui':['preview']}
    assert context['existing_functions']==['function f()']
    assert not project_parts.js_shared_reference_errors('app.loaded=true;app.busy=false;',source)
    assert project_parts.js_shared_reference_errors('app.fake=true;app.hidden=2;',source)
    assert json.loads(project_parts.js_contract_context(source,{'app':['loaded','busy'],'ui':[]}))['globals']=={'app':['loaded','busy'],'ui':[]}


def test_pinned_parser_files_match_retained_vendor_hashes():
    vendor=project_parts.ACORN_PATH.parent
    provenance=json.loads((vendor/'ACORN-PROVENANCE.json').read_text(encoding='utf-8'))
    assert provenance['name']=='acorn' and provenance['version']=='8.15.0'
    assert provenance['npm_integrity'].startswith('sha512-')
    for name,digest in provenance['files'].items():
        assert hashlib.sha256((vendor/name).read_bytes()).hexdigest()==digest
    assert 'MIT' in (vendor/'ACORN-LICENSE').read_text(encoding='utf-8')


@pytest.mark.asyncio
async def test_busy_feedback_names_actual_cancel_property_for_precise_model_patch():
    source='function setBusy(flag){\n app.busy=flag;\n ui.fileInput.disabled=flag;\n const blocked=flag||!app.loaded;\n'+''.join(' ui.'+key+'.disabled=blocked;\n' for key in ('playBtn','seekInput','startInput','endInput','exportBtn'))+' ui.cancelBtn.hidden=false;\n}'
    errors=await project_checks.inspect_helper(source,'busy')
    assert errors and all('cancelBtn.hidden expected true' in error and 'actual=false' in error for error in errors)
    assert project_patches.failing_lines(source,errors)==[10]


@pytest.mark.asyncio
async def test_helper_behavior_rejects_implicit_global_assignments():
    errors=await project_checks.inspect_helper('function setBusy(flag){app.busy=flag;blocked=flag||!app.loaded;}', 'busy')
    assert errors and any('blocked is not defined' in error for error in errors)
    assert await project_checks.inspect_helper('function setStatus(message){accidentalStatus=message;ui.status.textContent=message;}', 'status')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_raw_model_helper_keeps_code_and_provenance_without_json_envelope(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Helper','file':'app.js','kind':'js','task':'Write helper; laterHelper is supplied later','functions':['helper'],'include_html':False,'raw_source':True,'parameters':{'value':'Caller supplied data'}}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item,{'kind':'js','functions':['laterHelper']}],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    source='function helper(value) { return `🎬 ${value}`; }'
    async def model(messages,**options):
        assert 'fmt' not in options
        assert 'Output raw source only' in messages[0]['content']
        assert 'OWNER_GOAL:' not in messages[1]['content']
        assert 'CURRENT_HTML:' not in messages[1]['content']
        assert 'PARAMETER_CONTRACTS:' in messages[1]['content'] and 'Caller supplied data' in messages[1]['content']
        assert 'FUTURE_STANDALONE_HELPERS:' in messages[1]['content'] and 'laterHelper' in messages[1]['content']
        assert 'TASK:' in messages[1]['content']
        return {'content':source,'stats':{'finish_reason':'stop','served_model':backend}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==source and value['raw_source']==source
            assert value['evidence']['raw_sha256']==project_patches.digest(source)
            assert project_parts.reusable_part(value,{**item,'generation_contract_revision':2})
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('requested application',object(),event)


def test_callable_bindings_accept_arrows_without_rewriting_and_exclude_nested_names():
    source='const loaded = async (file) => { const nested = () => 9; return file; }; const ready = function inner() { return 4; };'
    assert project_parts.callable_names(source)==['loaded','ready']
    assert not project_parts.part_contract_errors(source,{'kind':'js','functions':['loaded','ready']})
    assert project_parts.callable_names('const loaded = 4; const obj = {ready(){}};')==[]
    item={'kind':'js','functions':['ready'],'behavior_checks':['status']}
    span='const ready = message => { return message; };'
    assert project_parts.select_model_helper('function extra(){return 2;} '+span,item)==span
    assert project_parts.select_model_helper('const ready = (a)=>a; const ready = (a)=>a+1;',item).count('ready')==2


@pytest.mark.asyncio
async def test_arrow_binding_still_requires_real_behavior():
    source='const setStatus = (message,isError=false) => { ui.status.textContent=message; ui.status.classList.toggle("error",isError); };'
    assert not await project_checks.inspect_helper(source,'status')
    assert await project_checks.inspect_helper('const setStatus = () => {};','status')


def test_shared_state_shadowing_is_rejected_but_first_declarations_remain_allowed():
    prior='const app={loaded:false};const ui={preview:null};'
    for source in ('function f(){const app={};}', 'const f = (ui) => ui;', 'function f(){const {app}=other;}', 'try{}catch(ui){}'):
        assert any('Do not shadow existing shared state' in error for error in project_parts.js_shared_reference_errors(source,prior))
    assert not project_parts.js_shared_reference_errors('function f(){const note="ui";app.loaded=true;}',prior)
    assert not project_parts.js_shared_reference_errors('const app={loaded:false};','')
    assert not project_parts.js_shared_reference_errors('const ui={preview:null};','const app={loaded:false};')


@pytest.mark.asyncio
async def test_release_urls_checks_actual_revocation_and_preserves_unrelated_state():
    assert await project_checks.inspect_helper('function releaseVideoUrls(){app.objectURL=null;app.downloadURL=null;}','release_urls')
    source='function releaseVideoUrls(){for(const key of ["objectURL","downloadURL"]){if(app[key])URL.revokeObjectURL(app[key]);app[key]=null;}}'
    assert not await project_checks.inspect_helper(source,'release_urls')
    assert await project_checks.inspect_helper(source.replace('app[key]=null;','app[key]=null;app.loaded=false;'),'release_urls')


@pytest.mark.asyncio
async def test_video_failure_requires_error_class_not_just_error_text():
    dependencies='function setBusy(flag){app.busy=flag;}function setStatus(message,error=false){ui.status.textContent=message;ui.status.classList.toggle("error",error);}'
    assert await project_checks.inspect_helper(dependencies+'function videoLoadFailed(){app.loaded=false;setBusy(false);setStatus("Video failed");}','video_load_error')
    assert not await project_checks.inspect_helper(dependencies+'function videoLoadFailed(){app.loaded=false;setBusy(false);setStatus("Video failed",true);}','video_load_error')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_shadowed_shared_state_requests_fresh_source_instead_of_patch(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    items=[{'name':'State','kind':'js','file':'app.js','task':'Declare app','raw_source':True,'include_html':False},
           {'name':'Helper','kind':'js','file':'app.js','task':'Update outer loaded','raw_source':True,'include_html':False,'functions':['helper']}]
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':items,'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    calls=[]
    responses=['const app={loaded:false};','function helper(){const app={};app.loaded=true;}','function helper(){app.loaded=true;}']
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==3:
            assert 'Write a fresh complete source part' in messages[1]['content']
            assert 'Do not shadow existing shared state app' in messages[1]['content']
        return {'content':responses[len(calls)-1],'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part' and value['index']==1:
            assert value['source']==responses[2]
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)
    assert len(calls)==3


def test_prompt_symbols_distinguish_outer_state_from_standalone_helpers():
    prior='const app={loaded:false,busy:false};const ui={preview:null};function setBusy(flag){}const unused=()=>2;'
    prompt=project_parts.js_prompt_context(prior,{'app':['loaded'],'ui':[]},['setBusy'])
    assert 'app.loaded' in prompt and 'app.busy' not in prompt and 'ui.preview' not in prompt
    assert 'setBusy(flag)' in prompt and 'function setBusy' not in prompt and 'unused' not in prompt
    assert 'not app/ui methods' in prompt and 'Keep existing app/ui objects' in prompt
    assert 'const app=' not in prompt and '"globals"' not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_document_asset_omission_uses_replayable_model_patch(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Document','kind':'document','file':'index.html','task':'Complete document with stylesheet and deferred script','tokens':250}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    raw='<!DOCTYPE html>\n<html>\n<head>\n<title>Model title</title>\n<meta name="viewport" content="width=device-width">\n<link rel="stylesheet" href="style.css">\n</head>\n<body>\n</body>\n</html>'
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:return {'content':raw,'stats':{'finish_reason':'stop'}}
        request=json.loads(messages[1]['content'])
        assert request['source']==project_parts.document_container(raw)
        line=request['source'].splitlines().index('</head>')+1
        return {'content':json.dumps({'edits':[{'line':line,'replace':'<script defer src="app.js"></script>\n</head>'}]}),'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert '<title>Model title</title>' in value['source'] and 'script defer' in value['source']
            assert value['origin_raw_source']==raw and len(value['repair_chain'])==1
            assert project_parts.reusable_part(value,item)['patched_source']==value['source']
            changed={**value,'origin_raw_source':raw.replace('Model title','Other title')}
            assert project_parts.reusable_part(changed,item) is None
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('app',object(),event)
    assert len(calls)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_indexed_patch_checks_line_boundaries_after_json_decoding(monkeypatch,backend):
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    replacement='quoted="🎬";\nnext();'
    async def model(messages,**options):
        if backend=='local':assert 'pattern' not in options['fmt']['json_schema']['schema']['properties']['edits']['items']['properties']['replace']
        return {'content':json.dumps({'edits':[{'line':1,'replace':replacement}]})}
    monkeypatch.setattr(llm,'chat',model)
    result=await project_patches.request('wrong();',task='repair',errors=['wrong'],contracts='',indexed=True)
    assert result.get('patch_validation_error')
    result=await project_patches.request('wrong();',task='repair HTML',errors=['wrong'],contracts='',indexed=True,single_line=False)
    assert not result.get('patch_validation_error')
    for replacement in ('quoted="🎬";\n','quoted="🎬";\r'):
        result=await project_patches.request('wrong();',task='repair',errors=['wrong'],contracts='',indexed=True)
        assert result.get('patch_validation_error')


def test_document_assets_only_report_missing_or_invalid_asset():
    style='<link rel="stylesheet" href="style.css">'
    script='<script src="app.js" defer></script>'
    assert not project_parts.document_asset_errors('<head>'+style+script+'</head><body></body>')
    errors=project_parts.document_asset_errors('<head>'+style+'</head><body></body>')
    assert len(errors)==1 and 'script' in errors[0] and 'stylesheet' not in errors[0]
    assert project_parts.document_asset_errors('<head>'+style+script.replace(' defer','')+'</head>')
    assert project_parts.document_asset_errors('<head>'+style+script.replace(' defer',' defer type="module"')+'</head>')
    assert project_parts.document_asset_errors('<head>'+style+'</head><body>'+script+'</body>')
    assert project_parts.document_asset_errors('<head>'+style+script+script+'</head>')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_document_patch_cannot_destroy_previously_valid_structure(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Document','kind':'document','file':'index.html','task':'Write complete document','tokens':250}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    raw='<!DOCTYPE html>\n<html>\n<head>\n<title>Title</title>\n<meta name="viewport" content="width=device-width">\n<link rel="stylesheet" href="style.css">\n</head>\n<body>\n</body>\n</html>'
    correct=raw.replace('</head>','<script defer src="app.js"></script>\n</head>')
    calls=[];events=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:return {'content':raw,'stats':{'finish_reason':'stop'}}
        if len(calls)==2:return {'content':json.dumps({'edits':[{'line':10,'replace':'Close body and html'}]}),'stats':{'finish_reason':'stop'}}
        assert 'Write a fresh complete source part' in messages[1]['content']
        return {'content':correct,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        events.append((kind,value))
        if kind=='source_part':
            assert value['source']==project_parts.document_container(correct) and not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('app',object(),event)
    assert any(kind=='code' and value.get('restored') and value['content']==project_parts.document_container(raw) for kind,value in events)
    assert len(calls)==3


@pytest.mark.asyncio
async def test_video_file_check_rejects_truthy_non_boolean_and_accepts_safe_mime_predicate():
    assert await project_checks.inspect_helper('function isVideoFile(file){return file&&file.type.startsWith("video/");}','video_file')
    assert await project_checks.inspect_helper('function isVideoFile(file){return true;}','video_file')
    assert not await project_checks.inspect_helper('function isVideoFile(file){return Boolean(file&&typeof file.type==="string"&&file.type.startsWith("video/"));}','video_file')


@pytest.mark.asyncio
async def test_video_callbacks_require_references_without_early_invocation():
    assert await project_checks.inspect_helper('function attachVideoHandlers(){ui.preview.onloadedmetadata=videoMetadataReady();ui.preview.onerror=videoLoadFailed();}','video_callbacks')
    assert not await project_checks.inspect_helper('function attachVideoHandlers(){ui.preview.onloadedmetadata=videoMetadataReady;ui.preview.onerror=videoLoadFailed;}','video_callbacks')


@pytest.mark.asyncio
async def test_video_source_check_requires_file_identity_and_hides_old_download():
    source='function setVideoSource(file){app.objectURL=URL.createObjectURL(file);app.filename=file.name;app.loaded=false;ui.downloadLink.hidden=true;ui.preview.src=app.objectURL;}'
    assert not await project_checks.inspect_helper(source,'video_source')
    assert await project_checks.inspect_helper(source.replace('URL.createObjectURL(file)','URL.createObjectURL(file.name)'),'video_source')
    assert await project_checks.inspect_helper(source.replace('ui.downloadLink.hidden=true;',''),'video_source')


def test_standalone_helper_calls_use_ast_not_comments_or_strings():
    names={'updateTimeline','setBusy'}
    source='function seekVideo(){const preview=ui.preview;preview.currentTime=2;preview.updateTimeline();}'
    errors=project_parts.standalone_helper_errors(source,names)
    assert len(errors)==1 and 'updateTimeline directly' in errors[0]
    assert not project_parts.standalone_helper_errors('function f(){updateTimeline();ui.preview.play();const text="preview.updateTimeline()";/* ui.setBusy() */}',names)
    assert project_parts.standalone_helper_errors('function f(){ui.preview["updateTimeline"]();}',names)
    assert not project_parts.standalone_helper_errors('function f(){window.updateTimeline();globalThis.setBusy(false);}',names)
    source='function f(){\n ui.preview.play();\n ui.preview.updateTimeline();\n}'
    assert project_patches.failing_lines(source,errors)==[3]


@pytest.mark.asyncio
async def test_playback_checks_reject_reversed_state_and_unhandled_play_rejection():
    source = """async function togglePlay(){
      if(!app.loaded||app.busy)return;
      const preview=ui.preview;
      if(!preview.paused){preview.pause();ui.playBtn.textContent='Play';return;}
      if(preview.currentTime<app.start||preview.currentTime>=app.end)preview.currentTime=app.start;
      try{await preview.play();ui.playBtn.textContent='Pause';}
      catch(error){setStatus(error.message,true);ui.playBtn.textContent='Play';}
    }"""
    assert not await project_checks.inspect_helper(source,'video_playback')
    assert await project_checks.inspect_helper(source.replace('if(!preview.paused)','if(preview.paused)'),'video_playback')
    assert await project_checks.inspect_helper(source.replace('setStatus(error.message,true);',''),'video_playback')
    assert await project_checks.inspect_helper(source.replace('await preview.play();','preview.play();'),'video_playback')
    assert await project_checks.inspect_helper('async function togglePlay(){while(true){await Promise.resolve();}}','video_playback')


@pytest.mark.asyncio
async def test_scrub_checks_numeric_strings_zero_clamping_and_busy_guards():
    source='function seekVideo(value){if(!app.loaded||app.busy)return;const time=Number(value);if(!Number.isFinite(time))return;ui.preview.currentTime=Math.max(0,Math.min(app.duration,time));updateTimeline();}'
    assert not await project_checks.inspect_helper(source,'video_seek')
    assert await project_checks.inspect_helper(source.replace('const time=Number(value);','const time=value;'),'video_seek')
    assert await project_checks.inspect_helper(source.replace('if(!app.loaded||app.busy)return;',''),'video_seek')
    assert await project_checks.inspect_helper(source.replace('updateTimeline();',''),'video_seek')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_missing_async_is_repaired_by_model_patch_with_provenance(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Await helper','file':'app.js','kind':'js','task':'Write async helper','functions':['helper'],'raw_source':True,'include_html':False}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    bad='function helper(){\n  await Promise.resolve();\n}'
    fixed='async '+bad;calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:return {'content':bad,'stats':{'finish_reason':'stop'}}
        request=json.loads(messages[1]['content'])
        assert request['numbered_lines']==[{'line':1,'text':'function helper(){'}]
        return {'content':json.dumps({'edits':[{'line':1,'replace':'async function helper(){'}]}),'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==fixed and value['origin_raw_source']==bad
            assert project_patches.replay(bad,value['repair_chain'],'app.js')==fixed
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)
    assert len(calls)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_noop_patch_keeps_valid_source_for_bounded_diagnosed_retry(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Predicate','file':'app.js','kind':'js','task':'Check video MIME safely','functions':['isVideoFile'],'raw_source':True,'include_html':False,'behavior_checks':['video_file']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    bad='function isVideoFile(file){return false;}'
    good='function isVideoFile(file){return Boolean(file&&typeof file.type==="string"&&file.type.startsWith("video/"));}'
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:content=bad
        elif len(calls)==2:content=json.dumps({'edits':[{'line':1,'replace':bad}]})
        elif len(calls)==3:
            assert json.loads(messages[1]['content'])['source']==bad
            content='The constant false rejects valid MIME types; inspect the File type safely.'
        else:
            request=json.loads(messages[1]['content'])
            assert request['source']==bad and 'repair_plan' in request
            content=json.dumps({'edits':[{'line':1,'replace':good}]})
        return {'content':content,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='source_part':
            assert value['source']==good and len(value['repair_chain'])==1
            assert project_patches.replay(bad,value['repair_chain'],'app.js')==good
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)
    assert len(calls)==4


@pytest.mark.asyncio
async def test_decomposed_playback_validates_callbacks_and_their_real_composition():
    started='function playbackStarted(){ui.playBtn.textContent="Pause";}'
    failed='function playbackFailed(error){setStatus(error.message,true);ui.playBtn.textContent="Play";}'
    start='function startPlayback(){const preview=ui.preview;if(preview.currentTime<app.start||preview.currentTime>=app.end)preview.currentTime=app.start;return preview.play().then(playbackStarted).catch(playbackFailed);}'
    pause='function pausePlayback(){ui.preview.pause();ui.playBtn.textContent="Play";}'
    toggle='function togglePlay(){if(!app.loaded||app.busy)return;if(ui.preview.paused)return startPlayback();pausePlayback();}'
    assert not await project_checks.inspect_helper(started,'video_play_started')
    assert not await project_checks.inspect_helper(failed,'video_play_failed')
    assert not await project_checks.inspect_helper(pause,'video_pause')
    assert not await project_checks.inspect_helper(started+failed+start,'video_start')
    assert not await project_checks.inspect_helper(started+failed+start+pause+toggle,'video_playback')
    assert await project_checks.inspect_helper(started.replace('Pause','Play'),'video_play_started')
    assert await project_checks.inspect_helper(failed.replace('error.message','"generic error"'),'video_play_failed')
    assert await project_checks.inspect_helper(started+failed+start.replace('.catch(playbackFailed)',''),'video_start')
    assert await project_checks.inspect_helper(started+failed+start.replace('preview.currentTime>=app.end','preview.currentTime>app.end'),'video_start')
    assert await project_checks.inspect_helper(pause.replace('pause()','play()'),'video_pause')


@pytest.mark.asyncio
async def test_trim_range_requires_finite_numbers_and_ordered_bounds():
    source='function isTrimRange(start,end,duration){return Number.isFinite(start)&&Number.isFinite(end)&&Number.isFinite(duration)&&start>=0&&end>start&&end<=duration;}'
    assert not await project_checks.inspect_helper(source,'trim_range')
    assert await project_checks.inspect_helper(source.replace('Number.isFinite','isFinite'),'trim_range')
    assert await project_checks.inspect_helper(source.replace('end>start','end>=start'),'trim_range')
    assert await project_checks.inspect_helper('function isTrimRange(){return true;}','trim_range')


@pytest.mark.asyncio
async def test_trim_composition_preserves_last_valid_bounds_and_busy_export_guard():
    predicate='function isTrimRange(start,end,duration){return Number.isFinite(start)&&Number.isFinite(end)&&Number.isFinite(duration)&&start>=0&&end>start&&end<=duration;}'
    apply='function applyTrim(start,end){app.start=start;app.end=end;ui.exportBtn.disabled=app.busy;setStatus(String(end-start)+" seconds");updateTimeline();return true;}'
    reject='function rejectTrim(){ui.exportBtn.disabled=true;setStatus("Invalid trim range",true);return false;}'
    validate='function validateTrim(){const start=Number(ui.startInput.value);const end=Number(ui.endInput.value);return isTrimRange(start,end,app.duration)?applyTrim(start,end):rejectTrim();}'
    assert not await project_checks.inspect_helper(apply,'trim_apply')
    assert not await project_checks.inspect_helper(reject,'trim_reject')
    assert not await project_checks.inspect_helper(predicate+apply+reject+validate,'video_trim')
    assert await project_checks.inspect_helper(apply.replace('disabled=app.busy','disabled=false'),'trim_apply')
    assert await project_checks.inspect_helper(reject.replace('return false;','app.start=0;return false;'),'trim_reject')
    assert await project_checks.inspect_helper(predicate+apply+reject+validate.replace('Number(ui.startInput.value)','ui.startInput.value'),'video_trim')


@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_repaired_runtime_error_can_reveal_later_assertions_without_rollback(monkeypatch,tmp_path,backend):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Apply trim','file':'app.js','kind':'js','task':'Apply validated trim and report duration','functions':['applyTrim'],'raw_source':True,'include_html':False,'behavior_checks':['trim_apply']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    monkeypatch.setattr(llm,'active_backend',lambda:backend)
    bad='function applyTrim(start,end){\n app.start=start;app.end=end;\n ui.exportBtn.disabled=busy;\n setStatus("Success",false);\n updateTimeline();return true;\n}'
    fixed=bad.replace('disabled=busy','disabled=app.busy').replace('setStatus("Success",false);','setStatus(String(end-start)+" seconds",false);')
    calls=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:content=bad
        elif len(calls)==2:content=json.dumps({'edits':[{'line':3,'replace':' ui.exportBtn.disabled=app.busy;'}]})
        elif len(calls)==3:
            request=json.loads(messages[1]['content'])
            assert 'disabled=app.busy' in request['source']
            content='The execution error is fixed; the status message still needs the selected numeric duration.'
        else:content=json.dumps({'edits':[{'line':4,'replace':' setStatus(String(end-start)+" seconds",false);'}]})
        return {'content':content,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='code' and value.get('restored'):
            pytest.fail('A repaired execution error must not be rolled back merely because later assertions can now run')
        if kind=='source_part':
            assert value['source']==fixed and len(value['repair_chain'])==2
            assert project_patches.replay(bad,value['repair_chain'],'app.js')==fixed
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)
    assert len(calls)==4


@pytest.mark.asyncio
async def test_helper_execution_errors_are_distinct_from_completed_assertions():
    errors=await project_checks.inspect_helper('function isVideoFile(file){return missingName;}','video_file')
    assert errors and all(e.startswith('Helper execution failed: ') for e in errors)
    assert project_patches.failing_lines('function f(){\n return missingName;\n}',errors)==[2]
    errors=await project_checks.inspect_helper('function isVideoFile(){return false;}','video_file')
    assert errors and all(e.startswith('Helper behavior failed: ') for e in errors)
    errors=await project_checks.inspect_helper('async function togglePlay(){throw new Error("unexpected failure");}','video_playback')
    assert errors and all(e.startswith('Helper execution failed: ') for e in errors)


@pytest.mark.asyncio
async def test_patch_introducing_execution_error_still_rolls_back(monkeypatch,tmp_path):
    recipes=tmp_path/'project_recipes';recipes.mkdir()
    item={'name':'Predicate','file':'app.js','kind':'js','task':'Check video MIME safely','functions':['isVideoFile'],'raw_source':True,'include_html':False,'behavior_checks':['video_file']}
    (recipes/'video_editor.json').write_text(json.dumps({'architecture':'','parts':[item],'panels':[],'required_ids':[]}))
    monkeypatch.setattr(project_parts,'__file__',str(tmp_path/'project_parts.py'))
    bad='function isVideoFile(file){return false;}'
    good='function isVideoFile(file){return Boolean(file&&typeof file.type==="string"&&file.type.startsWith("video/"));}'
    calls=[];restored=[]
    async def model(messages,**options):
        calls.append(messages)
        if len(calls)==1:content=bad
        elif len(calls)==2:content=json.dumps({'edits':[{'line':1,'replace':'function isVideoFile(file){return missingName;}'}]})
        else:
            assert 'Write a fresh complete source part' in messages[1]['content']
            content=good
        return {'content':content,'stats':{'finish_reason':'stop'}}
    monkeypatch.setattr(llm,'chat',model)
    class Validated(Exception):pass
    async def event(kind,value):
        if kind=='code' and value.get('restored'):restored.append(value['content'])
        if kind=='source_part':
            assert value['source']==good and not value.get('repair_chain')
            raise Validated()
    with pytest.raises(Validated):await project_parts.generate('application',object(),event)
    assert restored==[bad] and len(calls)==3


@pytest.mark.asyncio
async def test_trim_operations_preserve_state_and_compose_without_fixture_replacements():
    store='function storeTrim(start,end){app.start=start;app.end=end;}'
    export='function refreshTrimExport(){ui.exportBtn.disabled=app.busy;}'
    report='function reportTrim(start,end){setStatus(String(end-start)+" seconds",false);updateTimeline();}'
    apply='function applyTrim(start,end){storeTrim(start,end);refreshTrimExport();reportTrim(start,end);return true;}'
    assert not await project_checks.inspect_helper(store,'trim_store')
    assert not await project_checks.inspect_helper(export,'trim_export')
    assert not await project_checks.inspect_helper(report,'trim_report')
    assert not await project_checks.inspect_helper(store+export+report+apply,'trim_apply')
    assert await project_checks.inspect_helper(store.replace('app.end=end','app.end=start'),'trim_store')
    assert await project_checks.inspect_helper(export.replace('app.busy','false'),'trim_export')
    assert await project_checks.inspect_helper(report.replace('end-start','start-end'),'trim_report')

    for expression in ['start-end','(end-start)*10','(end-start)+0.01']:
        incorrect=report.replace('end-start',expression)
        assert await project_checks.inspect_helper(incorrect,'trim_report')
        assert await project_checks.inspect_helper(store+export+incorrect+apply,'trim_apply')

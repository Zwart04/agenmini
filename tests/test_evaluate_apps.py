"""Evaluator diagnostics must survive Windows console encodings."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_unicode_failure_report_prints_in_cp1252_without_losing_json_text():
    expected={'text':'Caption café 日本語 failed','meta':{'status':'failed'}}
    script='from scripts.evaluate_apps import print_case_result; print_case_result("video",'+repr(expected)+')'
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],
                          env={**os.environ,'PYTHONIOENCODING':'cp1252'},capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    output=result.stdout.decode('ascii').strip()
    assert output.startswith('CASE RESULT video ')
    assert json.loads(output.removeprefix('CASE RESULT video '))==expected
def test_failed_source_resume_requires_identical_recipe_and_exact_complete_original_text(tmp_path):
    import hashlib,json
    from scripts.evaluate_apps import failed_source_candidates
    from app import project_parts
    recipe=tmp_path/'recipe.json'
    item={'name':'Compute','file':'app.js','kind':'js','task':'Compute a value','functions':['compute'],'raw_source':True}
    recipe.write_text(json.dumps({'parts':[item]}),encoding='utf-8')
    previous=tmp_path/'old';attempts=previous/'attempts';attempts.mkdir(parents=True)
    report={'generator_source_sha256':{'app/project_recipes/video_editor.json':hashlib.sha256(recipe.read_bytes()).hexdigest()}}
    source='compute(value) {\n return value+1;\n}'
    attempt={'index':0,'part':'Compute','response_kind':'source','raw_source':source,'source':source,'stats':{'finish_reason':'stop','served_model':'local-test'}}
    path=attempts/'00-2.json';path.write_text(json.dumps(attempt))
    candidates=failed_source_candidates(previous,report,recipe,{})
    assert candidates[0]['source']==source and candidates[0]['evidence']['checkpoint_status'].startswith('failed')
    assert project_parts.reusable_part(candidates[0],{**item,'generation_contract_revision':2})['content']==source
    assert failed_source_candidates(previous,report,recipe,{0:{}})=={}
    for changed in [dict(attempt,source='function compute(value){return value+1;}'),
                    dict(attempt,stats={'finish_reason':'length'}),dict(attempt,response_kind='model_patch'),
                    dict(attempt,repair_chain=[{}]),dict(attempt,patch_error='Rejected'),dict(attempt,part='Other')]:
        path.write_text(json.dumps(changed));assert failed_source_candidates(previous,report,recipe,{})=={}
    path.write_text(json.dumps(attempt));recipe.write_text(json.dumps({'parts':[{**item,'task':'Different'}]}))
    assert failed_source_candidates(previous,report,recipe,{})=={}


def test_failed_resume_prefers_completed_behavior_checks_to_later_structural_failure(tmp_path):
    import hashlib
    from scripts.evaluate_apps import failed_source_candidates
    recipe=tmp_path/'recipe.json';recipe.write_text(json.dumps({'parts':[{'name':'Compute','kind':'js','file':'app.js','functions':['compute'],'task':'Compute result'}]}))
    report={'generator_source_sha256':{'app/project_recipes/video_editor.json':hashlib.sha256(recipe.read_bytes()).hexdigest()}}
    previous=tmp_path/'old';(previous/'attempts').mkdir(parents=True);(previous/'checks').mkdir()
    for attempt,source,errors in [(0,'function compute(){return 2;}',['Helper behavior failed: result expected 3; actual=2']),
                                  (2,'function compute(){return ui.video;}',['Undefined shared field ui.video; use the declared contracts.'])]:
        name=f'00-{attempt}.json'
        (previous/'attempts'/name).write_text(json.dumps({'index':0,'attempt':attempt,'part':'Compute','response_kind':'source','source':source,'raw_source':source,'stats':{'finish_reason':'stop'}}))
        (previous/'checks'/name).write_text(json.dumps({'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'passed':False,'errors':errors}))
    assert failed_source_candidates(previous,report,recipe,{})[0]['source']=='function compute(){return 2;}'
    (previous/'checks'/'00-0.json').write_text(json.dumps({'source_sha256':'tampered','errors':[]}))
    assert failed_source_candidates(previous,report,recipe,{})[0]['source']=='function compute(){return ui.video;}'

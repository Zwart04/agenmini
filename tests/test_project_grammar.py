import json
from app import project_grammar


def test_function_grammar_supplies_only_boundaries():
    item={'kind':'js','raw_source':True,'functions':['run'],'task':'Write async function run() with appropriate logic.'}
    grammar=project_grammar.function_boundary(item)
    assert '"async" space "function" space "run"' in grammar
    for implementation in ['app.','ui.','return','try','catch','captureStream','MediaRecorder']:
        assert implementation not in grammar
    assert 'block ::=' in grammar
    assert project_grammar.function_boundary({**item,'functions':['run','other']}) is None
    assert project_grammar.function_boundary({**item,'functions':['bad"name']}) is None
    assert project_grammar.function_boundary({**item,'preserve_literal_constants':True}) is None
    assert project_grammar.function_boundary({**item,'raw_source':False}) is None


def test_entrypoint_invocation_is_opt_in():
    item={'kind':'js','raw_source':True,'functions':['boot'],'task':'Connect DOM events.'}
    assert 'block ws\n' in project_grammar.function_boundary(item)
    assert 'block ws "boot" ws "(" ws ")"' in project_grammar.function_boundary({**item,'invoke_once':True})

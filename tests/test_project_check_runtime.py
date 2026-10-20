"""Slow host checks must stay bounded without treating every stall as bad code."""
import json
import subprocess
from types import SimpleNamespace
import pytest
from app import project_parts, project_checks


def test_contract_cache_returns_independent_values_and_includes_members(monkeypatch):
    calls=[]
    payload={'globals':{'app':['ready']},'existing_functions':['function run()'],
             'shadowed_state':[], 'shared_members':[['app','ready']],'called_methods':[]}
    def run(*args,**kwargs):
        calls.append(kwargs['input'])
        return SimpleNamespace(returncode=0,stdout=json.dumps(payload))
    project_parts._parsed_contract_json.cache_clear()
    monkeypatch.setattr(project_parts.subprocess,'run',run)
    first=project_parts.parsed_js_contracts('const app={ready:false};')
    first['globals']['app'].append('polluted')
    second=project_parts.parsed_js_contracts('const app={ready:false};',include_members=True)
    assert second==payload and len(calls)==1
    project_parts._parsed_contract_json.cache_clear()


@pytest.mark.parametrize('failure',['timeout','syntax','bad_json'])
def test_contract_cache_does_not_remember_failed_reads(monkeypatch,failure):
    calls=[]
    payload={'globals':{},'existing_functions':[],'shadowed_state':[], 'shared_members':[],'called_methods':[]}
    def run(*args,**kwargs):
        calls.append(1)
        if len(calls)==1:
            if failure=='timeout':raise subprocess.TimeoutExpired('node',3)
            return SimpleNamespace(returncode=1 if failure=='syntax' else 0,stdout='bad json')
        return SimpleNamespace(returncode=0,stdout=json.dumps(payload))
    project_parts._parsed_contract_json.cache_clear()
    monkeypatch.setattr(project_parts.subprocess,'run',run)
    assert project_parts.parsed_js_contracts('function later(){}') is None
    assert project_parts.parsed_js_contracts('function later(){}',include_members=True)==payload
    assert len(calls)==2
    project_parts._parsed_contract_json.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize('second_result,passed',[
    ('[kode keluar 0]\nbehavioral helper check passed',True),
    ('[kode keluar 1]\n{"helper_timeout":true,"message":"Script execution timed out after 2000ms"}',False),
    ('[kode keluar 1]\n{"helper_failures":["wrong value"]}',False),
])
async def test_vm_stall_retries_unchanged_source_once(monkeypatch,second_result,passed):
    calls=[]
    async def run(command,**kwargs):
        calls.append(kwargs)
        return '[kode keluar 1]\n{"helper_timeout":true,"message":"Script execution timed out after 500ms"}' if len(calls)==1 else second_result
    monkeypatch.setattr(project_checks.tools,'_run_sandboxed',run)
    result=await project_checks.inspect_helper('function f(){}','status')
    assert bool(result)!=passed and len(calls)==2
    first=json.loads(calls[0]['stdin']);second=json.loads(calls[1]['stdin'])
    assert second.pop('timeoutMs')==2000 and first==second
    assert calls[1]['timeout']==8


@pytest.mark.asyncio
async def test_real_behavior_failure_does_not_retry_as_host_stall(monkeypatch):
    calls=[]
    async def run(command,**kwargs):
        calls.append(1)
        return '[kode keluar 1]\n{"helper_failures":["missing status"]}'
    monkeypatch.setattr(project_checks.tools,'_run_sandboxed',run)
    assert await project_checks.inspect_helper('function f(){}','status')==['Helper behavior failed: missing status']
    assert len(calls)==1


@pytest.mark.asyncio
async def test_real_infinite_model_code_remains_bounded():
    result=await project_checks.inspect_helper('function normalizeSeconds(){while(true){}}','normalize_seconds')
    assert result and 'timed out' in ' '.join(result)

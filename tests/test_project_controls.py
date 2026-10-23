import json
from pathlib import Path

import pytest

from app import db, project_checks, project_parts, projects
from app.project_control_checks import CONTROL_CASES


def test_control_recipe_has_checked_ordered_dependencies():
    recipe=json.loads((Path(project_parts.__file__).parent/'project_recipes/video_editor.json').read_text(encoding='utf-8'))
    available=set()
    controls=[]
    for part in recipe['parts']:
        assert set(part.get('behavior_dependencies',[]))<=available
        assert set(part.get('behavior_checks',[]))<=project_checks.CHECKS
        available.update(part.get('functions',[]))
        if any(check in CONTROL_CASES for check in part.get('behavior_checks',[])):
            assert len(part['functions'])==1
            controls.append(part['functions'][0])
    assert len(controls)==24
    assert controls[-1]=='initEditor'
    dependencies={fn:set(part.get('behavior_dependencies',[])) for part in recipe['parts'] for fn in part.get('functions',[])}
    for part in recipe['parts']:
        if not any(check in CONTROL_CASES for check in part.get('behavior_checks',[])):continue
        chosen=set(part.get('behavior_dependencies',[]))
        for name in chosen:
            assert dependencies[name]<=chosen, 'Control fixture must include transitive model helpers for '+name
    item=next(part for part in recipe['parts'] if part.get('invoke_once'))
    source='function initEditor() {}\ninitEditor();'
    assert project_parts.select_model_helper(source,item)==source


@pytest.mark.asyncio
@pytest.mark.parametrize('check',list(CONTROL_CASES))
async def test_control_checks_reject_empty_or_noop_implementation(check):
    name=check.removeprefix('video_controls_')
    source='function '+name+'() {}'
    assert await project_checks.inspect_helper(source,check)


@pytest.mark.asyncio
async def test_control_checks_reject_immediate_actions_and_dropped_events():
    check='video_controls_bindTrimControls'
    good="function bindTrimControls(){ui.startInput.addEventListener('change',validateTrim);ui.endInput.addEventListener('change',validateTrim);ui.titleInput.addEventListener('input',updateText);}"
    assert await project_checks.inspect_helper(good,check)==[]
    assert await project_checks.inspect_helper(good.replace("'change'","'input'"),check)==[]
    assert await project_checks.inspect_helper(good.replace("addEventListener('change',validateTrim)","addEventListener('change',validateTrim())"),check)
    assert await project_checks.inspect_helper(good.replace("ui.endInput.addEventListener('change',validateTrim);",''),check)


@pytest.mark.asyncio
async def test_initializer_is_run_and_checked_exactly_once():
    groups=['bindImportControls','bindTrimControls','bindExportControls','bindPreviewControls','bindEditorControls']
    source='function initEditor(){'+''.join(name+'();' for name in groups)+"setBusy(false);updateText();setStatus('Import a video');}"
    check='video_controls_initEditor'
    assert await project_checks.inspect_helper(source+'initEditor();',check)==[]
    assert await project_checks.inspect_helper(source,check)
    assert await project_checks.inspect_helper(source+'initEditor();initEditor();',check)
    assert await project_checks.inspect_helper(source.replace('setBusy(false)',"setBusy('false')")+'initEditor();',check)


@pytest.mark.asyncio
async def test_existing_opt_out_keeps_normal_project_path(monkeypatch):
    original=db.setting
    monkeypatch.setattr(db,'setting',lambda key: '0' if key=='coding_parts_experimental' else original(key))
    async def forbidden(*args,**kwargs):raise AssertionError('part generation opted out')
    monkeypatch.setattr(project_parts,'generate',forbidden)
    class NormalPath(Exception):pass
    async def planned(*args,**kwargs):raise NormalPath()
    monkeypatch.setattr(projects.structured,'request',planned)
    with pytest.raises(NormalPath):await projects.generate('Build video editor with export',object())

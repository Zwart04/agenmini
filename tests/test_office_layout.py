import json
import shutil
import subprocess
from pathlib import Path
import pytest


def test_office_active_idle_and_waiting_positions_fit_small_screens():
    if not shutil.which('node'):pytest.skip('Node unavailable')
    source=Path('frontend/office.js').read_text()
    cases=[]
    for width in (288,358,398,936):
        for count in (2,10,30):
            for status in ('idle','waiting','working'):
                bots=[{'id':str(i),'status':status} for i in range(count)]
                tasks=[{'source':'0','target':'1','status':'working'}] if status=='working' else []
                cases.append({'width':width,'d':{'bots':bots,'tasks':tasks}})
    code=source+'\nconst cases='+json.dumps(cases)+';console.log(JSON.stringify(cases.map(c=>({width:c.width,...officePlacement(c.d,c.width)}))));'
    result=subprocess.run(['node','-e',code],text=True,capture_output=True,check=True,timeout=10)
    for layout in json.loads(result.stdout):
        for entry in layout['positions']:
            point=entry['point']
            assert point['x']-43>=0 and point['x']+43<=layout['width']
            assert point['y']-32>=0 and point['y']-32+112<=layout['height'],layout

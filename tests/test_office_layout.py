import json
import shutil
import subprocess
from pathlib import Path
import pytest


def test_office_active_idle_and_waiting_positions_fit_small_screens():
    if not shutil.which('node'):pytest.skip('Node unavailable')
    source=Path('frontend/office.js').read_text()
    cases=[]
    for width in (252,284,330,358,398,720,936,1104):
        for count in (2,10,30):
            for status in ('idle','waiting','working'):
                bots=[{'id':str(i),'status':status} for i in range(count)]
                tasks=[{'source':str(i),'target':str(i+1),'status':'working'} for i in range(count-1)] if status=='working' else []
                cases.append({'width':width,'d':{'bots':bots,'tasks':tasks}})
    code=source+'\nconst cases='+json.dumps(cases)+';console.log(JSON.stringify(cases.map(c=>({width:c.width,...officePlacement(c.d,c.width)}))));'
    result=subprocess.run(['node'],input=code,text=True,encoding='utf-8',capture_output=True,check=True,timeout=10)
    for layout in json.loads(result.stdout):
        for entry in layout['positions']:
            point=entry['point']
            assert point['x']-43>=0 and point['x']+43<=layout['width']
            assert point['y']-32>=0 and point['y']-32+112<=layout['height'],layout

        # Names/actions occupy 86 x 112 pixels. No shared waiting/meeting slot.
        positions=layout['positions']
        for i,a in enumerate(positions):
            for b in positions[i+1:]:
                assert abs(a['point']['x']-b['point']['x'])>=86 or abs(a['point']['y']-b['point']['y'])>=112,layout

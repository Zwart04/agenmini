"""Check executable UI scripts, including the inline script hosting navigation."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node is needed to parse browser JavaScript')
def test_all_browser_javascript_parses():
    root = Path(__file__).resolve().parents[1] / 'frontend'
    scripts = [(path.name, path.read_text()) for path in root.glob('*.js')]
    scripts += [('index.html inline', script) for script in
                re.findall(r'<script>(.*?)</script>', (root / 'index.html').read_text(), re.S)]
    for name, source in scripts:
        result = subprocess.run(['node', '--check'], input=source, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, name + ': ' + result.stderr


def test_frontend_asset_paths_and_load_order():
    from html.parser import HTMLParser
    from app import config
    class Assets(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            value=dict(attrs).get('src' if tag=='script' else 'href','')
            if value.startswith('/static/'):self.paths.append(value.removeprefix('/static/'))
    root=Path(__file__).resolve().parents[1]/'frontend'
    assert config.STATIC_DIR==root
    parser=Assets();html=(root/'index.html').read_text();parser.feed(html)
    assert '<style>' not in html and '<script>' not in html
    assert parser.paths[:5]==['theme.css','base.css','control.css','office.css','layout.css']
    assert parser.paths[5]=='app.js' and parser.paths[-1]=='navigation.js'
    assert all((root/name).is_file() for name in parser.paths)

def test_learning_and_setup_controls_belong_to_their_visible_panels():
    from html.parser import HTMLParser
    class Panels(HTMLParser):
        def __init__(self):super().__init__();self.stack=[];self.nodes={}
        def handle_starttag(self,tag,attrs):
            a=dict(attrs);ancestors=[x[1].get('id') for x in self.stack]
            if a.get('id'):self.nodes[a['id']]=(a,ancestors)
            if tag not in ('input','img','br','hr','meta','link'):self.stack.append((tag,a))
        def handle_endtag(self,tag):
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    p=Panels();p.feed((Path(__file__).resolve().parents[1]/'frontend/index.html').read_text())
    for name in ('learningInfo','learningCandidates','trainingExport'):
        assert 'v-skills' in p.nodes[name][1]
    for name,setting in (('harnessMode','harness_mode'),('selfImprove','self_improve')):
        attrs,parents=p.nodes[name];assert 'setForm' in parents and attrs['name']==setting
    assert 'v-ai' in p.nodes['setupGuide'][1]

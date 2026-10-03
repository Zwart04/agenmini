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

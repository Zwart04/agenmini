"""Check executable UI scripts, including the inline script hosting navigation."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node is needed to parse browser JavaScript')
def test_all_browser_javascript_parses():
    root = Path(__file__).resolve().parents[1] / 'app' / 'static'
    scripts = [(path.name, path.read_text()) for path in root.glob('*.js')]
    scripts += [('index.html inline', script) for script in
                re.findall(r'<script>(.*?)</script>', (root / 'index.html').read_text(), re.S)]
    for name, source in scripts:
        result = subprocess.run(['node', '--check'], input=source, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, name + ': ' + result.stderr

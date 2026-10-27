"""Static download portal: publish links only for assets that exist on GitHub."""
import argparse
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT=Path(__file__).resolve().parent


def build():
    parser=argparse.ArgumentParser();parser.add_argument('--release-json',type=Path);args=parser.parse_args()
    if args.release_json:release=json.loads(args.release_json.read_text())
    else:
        headers={'User-Agent':'AgenMini-Website'}
        if os.environ.get('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
        request=urllib.request.Request('https://api.github.com/repos/Zwart04/agenmini/releases/latest',headers=headers)
        with urllib.request.urlopen(request,timeout=60) as response:release=json.load(response)
    if release.get('draft') or release.get('prerelease'):raise ValueError('Only stable public releases can be advertised')
    assets=[{'name':a['name'],'url':a['browser_download_url'],'size':a['size']} for a in release['assets']]
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    for name in ('index.html','site.css','site.js'):shutil.copy2(ROOT/name,output/name)
    (output/'assets').mkdir(exist_ok=True)
    shutil.copy2(ROOT.parent/'frontend/mascot.png',output/'assets/mascot.png')
    for name in ('workbench-desktop.webp','workbench-mobile.webp','workbench-desktop.png','workbench-mobile.png'):
        shutil.copy2(ROOT.parent/'docs/screenshots'/name,output/'assets'/name)
    (output/'assets/workbench.jpg').unlink(missing_ok=True)
    (output/'release.json').write_text(json.dumps({'tag':release['tag_name'],'assets':assets},indent=2))
    (output/'.nojekyll').write_text('')
    print('Website ready:',output,release['tag_name'],len(assets),'real release assets')


if __name__=='__main__':build()

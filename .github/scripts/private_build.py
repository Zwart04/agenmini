"""Attach verified binary builds to a private draft, bound to one exact commit.

Private preview builds use release storage, so a full Actions artifact store
cannot prevent the actual tests from running. Never runs for public repos/PRs.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def gh(*args, check=True):
    return subprocess.run(['gh',*args],check=check,text=True,capture_output=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('group',choices=('gateway','windows','linux'));group=parser.parse_args().group
    repo=os.environ['GITHUB_REPOSITORY'];sha=os.environ['GITHUB_SHA']
    if repo!='Zwart04/agenmini' or os.environ.get('GITHUB_EVENT_NAME')!='push':raise SystemExit('Private preview upload is restricted to owner pushes.')
    if json.loads(gh('api','repos/'+repo).stdout).get('private') is not True:raise SystemExit('Repository must be private.')
    version=re.search(r'VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"',Path('app/__init__.py').read_text())[1]
    tag='v'+version
    view=gh('release','view',tag,'--repo',repo,'--json','isDraft,targetCommitish',check=False)
    if view.returncode:
        gh('release','create',tag,'--repo',repo,'--draft','--target',sha,'--title','Agen Mini '+tag+' — private validation','--notes','Private candidate. Binary tests must pass before the draft can be published.',check=False)
        view=gh('release','view',tag,'--repo',repo,'--json','isDraft,targetCommitish')
    draft=json.loads(view.stdout)
    if not draft['isDraft'] or draft['targetCommitish']!=sha:raise SystemExit('Draft must target this exact commit; published or mismatched releases are never overwritten.')
    patterns={'gateway':['gateway-dist/agenmini-gateway-*'],'windows':['dist/agenmini-setup-*-windows-x64.exe*','dist/agenmini-*-windows-x64.zip*'],'linux':['dist/*.deb*','dist/*.rpm*','dist/*.pkg.tar.zst*','dist/*-linux-*.tar.gz*']}[group]
    files=sorted({p for pattern in patterns for p in Path('.').glob(pattern)})
    if not files or any(not p.is_file() or p.is_symlink() or not re.fullmatch(r'[A-Za-z0-9._-]+',p.name) for p in files):raise SystemExit('Invalid or empty build payload.')
    # All callers run this after their complete test sequence has succeeded.
    result=gh('release','upload',tag,*map(str,files),'--repo',repo,'--clobber',check=False)
    if result.returncode:raise SystemExit('Private build upload failed; no test result was overridden.')
    print('Verified private build files uploaded:',group,len(files),tag,sha[:12])


if __name__=='__main__':main()

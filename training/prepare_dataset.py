"""Validate, deduplicate and split owner-reviewed answer SFT data without ML dependencies."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(source, output):
    rows={}
    for line in Path(source).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        row=json.loads(line);messages=row.get('messages')
        if not isinstance(messages,list) or len(messages)!=2 or [m.get('role') for m in messages]!=['user','assistant']:
            raise ValueError('Expected an owner-reviewed user/assistant answer pair.')
        if any(not isinstance(m.get('content'),str) or not m['content'].strip() for m in messages):raise ValueError('Empty/non-text message.')
        # Group repeated user questions in the same split to avoid train/validation leakage.
        key=' '.join(messages[0]['content'].lower().split())
        rows.setdefault(key,{'messages':messages})
    if len(rows)<10:raise ValueError('At least 10 distinct reviewed questions are needed even for a smoke experiment, not a quality guarantee.')
    ordered=sorted(rows,key=lambda key:hashlib.sha256(key.encode()).hexdigest())
    count=max(1,len(ordered)//10);sets={'validation':ordered[:count],'train':ordered[count:]}
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Use an empty output directory; datasets are not overwritten.')
    output.mkdir(parents=True,exist_ok=True)
    for name,keys in sets.items():
        (output/(name+'.jsonl')).write_text(''.join(json.dumps(rows[k],ensure_ascii=False)+'\n' for k in keys),encoding='utf-8')
    manifest={'format':'answer-sft','examples':len(rows),'train':len(sets['train']),'validation':len(sets['validation']),
              'source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),
              'note':'Review private content manually. No synthetic tool calls, benchmark scores or weight training are generated.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args();print(json.dumps(prepare(args.source,args.output)))

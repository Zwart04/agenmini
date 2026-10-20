"""Constrain source boundaries for a local decoder; never supply a function body.

This is a balanced-text format, not a JavaScript parser. Acorn/Node and behavior
checks still decide whether the model's implementation is valid.
"""
import json
import re

_BODY = r'''
ws ::= [ \t\r\n]{0,8}
space ::= [ \t]{1,4}
params ::= [^(){}\r\n]*
block ::= "{" piece* "}"
piece ::= block | double | single | template | [^{}"'`/]+ | "/" [^/*{}"'`]
double ::= "\"" ([^"\\\r\n] | "\\" [^\r\n])* "\""
single ::= "'" ([^'\\\r\n] | "\\" [^\r\n])* "'"
template ::= "`" ([^`\\] | "\\" [^\r\n])* "`"
'''


def function_boundary(item):
    names=item.get('functions',[])
    if item.get('kind')!='js' or not item.get('raw_source') or len(names)!=1 or item.get('preserve_literal_constants'):
        return None
    name=names[0]
    if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*',name):return None
    task=item.get('task','')+' '+item.get('system_contract','')
    asynchronous=bool(re.search(r'\basync\s+function\s+'+re.escape(name)+r'\b',task))
    prefix='"async" space ' if asynchronous else '("async" space)? '
    invocation=' '+json.dumps(name)+' ws "(" ws ")" ";"? ws' if item.get('invoke_once') else ''
    return 'root ::= '+prefix+'"function" space '+json.dumps(name)+' ws "(" params ")" ws block ws'+invocation+'\n'+_BODY

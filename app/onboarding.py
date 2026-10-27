"""Validate a deliberate local/online setup before changing saved preferences."""
import hashlib
import json
import os
from urllib.parse import urlparse
from . import db


def managed_local():
    return os.name!='nt' and os.environ.get('AGENMINI_DESKTOP')!='1'


def endpoint(value, local=False):
    if not isinstance(value,str) or len(value)>1000:raise ValueError('Alamat model tidak valid.')
    parsed=urlparse(value)
    try:port=parsed.port
    except ValueError:raise ValueError('Port model tidak valid.') from None
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (port is not None and not 1<=port<=65535):raise ValueError('Isi URL http/https tanpa kredensial, query, atau fragmen.')
    if local and parsed.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Model lokal harus memakai localhost, 127.0.0.1, atau ::1.')
    if not parsed.path.rstrip('/').endswith('/v1'):raise ValueError('Endpoint model harus diakhiri /v1.')
    return value.rstrip('/')


def plan(data):
    source=data.get('source')
    if source is None:return None
    if source not in ('local','online'):raise ValueError('Pilih AI Lokal atau Online dahulu.')
    method=data.get('connection')
    if method=='managed' and source=='local' and managed_local():
        from . import local_models
        model=data.get('local_model')
        if not any(row['id']==model and row['fits'] for row in local_models.catalogue()['models']):raise ValueError('Pilih model lokal yang sesuai dengan RAM mesin ini.')
        return {'source':source,'backend':'local','model':model,'settings':{'local_model_id':model}}
    if method=='gateway' and source=='online':
        model=data.get('model')
        if not isinstance(model,str) or not model.strip():raise ValueError('Hubungkan provider lalu pilih model dahulu.')
        return {'source':source,'backend':'router','model':model,'settings':{'router_last_model':model,'model':model}}
    if method!='direct':raise ValueError('Pilih cara menghubungkan AI.')
    url=endpoint(data.get('url',''),local=source=='local')
    model=data.get('model')
    key=data.get('api_key','')
    if not isinstance(model,str) or not 1<=len(model.strip())<=200 or any(ord(c)<32 for c in model):raise ValueError('Isi ID model dari server/provider.')
    if not isinstance(key,str) or len(key)>8192 or '\n' in key or '\r' in key:raise ValueError('API key tidak valid.')
    return {'source':source,'backend':'online','model':model.strip(),'settings':{'online_base':url,'online_key':key,'online_model':model.strip()}}


def fingerprint():
    backend=db.setting('llm_backend')
    fields=['llm_backend','online_base','online_key','online_model'] if backend=='online' else ['llm_backend','router_last_model','compatible_key'] if backend=='router' else ['llm_backend','local_model_id']
    return hashlib.sha256(json.dumps([db.setting(k) for k in fields]).encode()).hexdigest()


def apply(choice):
    from . import runtime_status
    if not choice.get('already_preparing'):
        runtime_status.request('local' if choice['backend']=='local' else 'api', choice['model'] if choice['backend']=='local' else None)
    for key,value in choice['settings'].items():db.set_setting(key,value)
    db.set_setting('llm_backend',choice['backend'])
    db.set_setting('setup_ai_source',choice['source'])
    db.set_setting('auto_9router','0')
    db.set_setting('auto_local','0')
    db.set_setting('setup_connection_pending',fingerprint())
    db.set_setting('setup_complete','0')


def verified(backend,model):
    expected=db.setting('online_model') if backend=='online' else db.setting('router_last_model') if backend=='router' else db.setting('local_model_id')
    if backend==db.setting('llm_backend') and model==expected and db.setting('setup_connection_pending')==fingerprint():
        db.set_setting('setup_complete','1')
        db.set_setting('setup_connection_verified',fingerprint())
        db.set_setting('setup_connection_pending','')

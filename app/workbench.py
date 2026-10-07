"""Bounded workspace editor and private live harness journal API."""
import hashlib
import os
import re
import tempfile
import time
from pathlib import PurePosixPath
from aiohttp import web
from . import config, db, tools

routes=web.RouteTableDef()
EXTENSIONS={'.html','.css','.js','.json','.md','.txt','.py','.ts','.tsx','.jsx','.svg','.sql','.toml','.yml','.yaml','.sh'}

def readable_name(name):
    parts=PurePosixPath(str(name).replace('\\','/')).parts
    return bool(parts) and not any(p.startswith('.') or p in ('node_modules','__pycache__','venv','dist') or
        re.search(r'(?:secret|credential|token|password|private.?key)',p,re.I) for p in parts) and PurePosixPath(name).suffix.lower() in EXTENSIONS

def target(name):
    if not readable_name(name):raise ValueError('Berkas ini tidak tersedia pada editor.')
    path=tools._workpath(name)
    if path.exists() and (not path.is_file() or path.stat().st_size>200000):raise ValueError('Batas editor 200 KB per berkas.')
    return path

def file_info(name):
    path=target(name)
    if not path.is_file():raise FileNotFoundError('Berkas belum ada.')
    content=path.read_text(encoding='utf-8')
    return {'path':name,'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest()}

@routes.get('/api/workbench/files')
async def files(request):
    result=[]
    root=config.WORK_DIR.resolve()
    # Prune large/private trees, no traversal through symlink directories.
    for parent, dirs, names in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in ('node_modules','__pycache__','venv','dist') and not ( __import__('pathlib').Path(parent)/d).is_symlink()]
        for name in names:
            p=__import__('pathlib').Path(parent)/name
            relative=p.relative_to(root).as_posix()
            if p.is_symlink() or not readable_name(relative) or p.stat().st_size>200000:continue
            result.append(relative)
            if len(result)>=300:return web.json_response({'files':sorted(result),'truncated':True})
    return web.json_response({'files':sorted(result),'truncated':False})

@routes.get('/api/workbench/file')
async def read(request):
    try:return web.json_response(file_info(request.query.get('path','')))
    except FileNotFoundError as exc:return web.json_response({'error':str(exc)},status=404)
    except (ValueError,UnicodeError) as exc:return web.json_response({'error':str(exc)},status=400)

@routes.post('/api/workbench/file')
async def save(request):
    data=await request.json()
    try:
        path=target(data.get('path',''));content=data.get('content')
        if not isinstance(content,str) or len(content.encode())>200000:raise ValueError('Isi editor tidak valid/terlalu besar.')
        old=file_info(data['path'])
        if old['sha256']!=data.get('sha256'):return web.json_response({'error':'Berkas berubah di server. Muat ulang dan tinjau sebelum menyimpan.'},status=409)
        backups=config.DATA_DIR/'editor-backup';backups.mkdir(parents=True,exist_ok=True)
        (backups/(str(time.time_ns())+'.txt')).write_text(old['content'],encoding='utf-8')
        for stale in sorted(backups.glob('*.txt'))[:-100]:stale.unlink()
        fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.editor-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as out:out.write(content);out.flush();os.fsync(out.fileno())
            os.chmod(temp,path.stat().st_mode & 0o777)
            try:os.chown(temp,config.KERJA_UID,config.KERJA_GID)
            except (AttributeError,OSError):pass
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return web.json_response(file_info(data['path']))
    except (ValueError,UnicodeError,FileNotFoundError) as exc:return web.json_response({'error':str(exc)},status=400)

@routes.get('/api/workbench/events/{chat_id}')
async def journal(request):
    from .deepseek_core import events
    try:
        cid=int(request.match_info['chat_id']);after=max(0,int(request.query.get('after','0')))
        if not db.one('SELECT id FROM chats WHERE id=?',(cid,)):raise ValueError('Percakapan tidak ada.')
        return web.json_response({'events':events(cid,after)})
    except ValueError as exc:return web.json_response({'error':str(exc)},status=400)

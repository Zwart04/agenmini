"""Fixed, opt-in host requests; Docker/root access stays in the host supervisor."""
import json, os
from pathlib import Path
from . import config, db

def status():
    path=config.DATA_DIR/'hardware.json'
    try:hardware=json.loads(path.read_text())
    except (OSError,ValueError):hardware={}
    ram=hardware.get('ram_mb',0);swap=hardware.get('swap_mb',0)
    recommended=4 if 0<ram<2048 else 2 if 0<ram<8192 else 0
    return {'managed':os.name!='nt' and Path('/.dockerenv').is_file() and bool(ram),
            'ram_mb':ram,'swap_mb':swap,'recommended_swap_gb':0 if swap else recommended,
            'pending':(config.DATA_DIR/'host-setup-request.json').exists(),'result':read_result()}

def read_result():
    try:return json.loads((config.DATA_DIR/'host-setup-status.json').read_text())
    except (OSError,ValueError):return {}

def request(swap_gb=0,harness_memory=False,retry=''):
    if type(swap_gb)!=int or swap_gb not in (0,2,4,8) or type(harness_memory)!=bool:
        raise ValueError('Pilihan RAM/swap tidak valid.')
    if not isinstance(retry,str):raise ValueError('Runtime tidak valid.')
    if retry and not harness_memory:raise ValueError('Coba ulang runtime memerlukan pilihan resource harness.')
    if not status()['managed']:raise ValueError('Pengaturan host tersedia pada instalasi VPS dengan supervisor. Windows memakai virtual memory sistem.')
    if harness_memory and status()['ram_mb']<2560:raise ValueError('Harness asli memerlukan setidaknya 2,5 GB RAM fisik agar aplikasi dan pemasang memiliki ruang. Gunakan Agen Mini bawaan; swap tidak menggantikan syarat RAM ini.')
    if retry:
        from .harnesses import entry
        if not entry(retry).get('kind'):raise ValueError('Runtime tidak valid.')
    target=config.DATA_DIR/'host-setup-request.json'
    if target.exists():raise ValueError('Pengaturan host sebelumnya masih menunggu supervisor.')
    pending=target.with_suffix('.pending')
    pending.write_text(json.dumps({'swap_gb':swap_gb,'harness_memory':harness_memory,'retry':retry}))
    pending.replace(target)
    return {'message':'Menunggu supervisor. Status diperbarui di halaman; restart container hanya dilakukan saat aplikasi senggang.'}

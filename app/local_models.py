"""Curated CPU GGUF catalogue, metadata verified on 2026-10-02."""
import json, os, platform
from . import config
CATALOG = [
 {'id':'qwenpaw-2b','name':'QwenPaw Flash 2B','repo':'agentscope-ai/QwenPaw-Flash-2B-Q4_K_M','file':'QwenPaw-flash-2B-20260330-q4.gguf','download_gb':1.3,'min_ram_gb':4,'runtime_mb':2300,'rank':2,'note':'Pilihan agen ringan; smoke test model nyata tersedia.'},
 {'id':'qwen35-08b','name':'Qwen3.5 0.8B','repo':'bartowski/Qwen_Qwen3.5-0.8B-GGUF','file':'Qwen_Qwen3.5-0.8B-Q4_K_M.gguf','download_gb':0.58,'min_ram_gb':3,'runtime_mb':1700,'rank':1,'note':'Paling hemat; tugas kompleks lebih mudah salah.'},
 {'id':'qwen35-2b','name':'Qwen3.5 2B','repo':'bartowski/Qwen_Qwen3.5-2B-GGUF','file':'Qwen_Qwen3.5-2B-Q4_K_M.gguf','download_gb':1.4,'min_ram_gb':5,'runtime_mb':3000,'rank':3,'note':'Keluarga baru untuk tugas umum; kualitas perlu diuji pada tugas Anda.'},
 {'id':'qwen35-4b','name':'Qwen3.5 4B','repo':'bartowski/Qwen_Qwen3.5-4B-GGUF','file':'Qwen_Qwen3.5-4B-Q4_K_M.gguf','download_gb':3.01,'min_ram_gb':8,'runtime_mb':5500,'rank':4,'note':'Kandidat kualitas lebih tinggi; CPU lebih lambat.'},
 {'id':'qwen35-9b','name':'Qwen3.5 9B','repo':'bartowski/Qwen_Qwen3.5-9B-GGUF','file':'Qwen_Qwen3.5-9B-Q4_K_M.gguf','download_gb':6.17,'min_ram_gb':16,'runtime_mb':11000,'rank':5,'note':'Kandidat kapasitas terbesar dalam katalog; bukan jaminan paling pintar.'},
]

def hardware():
    path = config.DATA_DIR / 'hardware.json'
    if path.exists():
        try: return {**json.loads(path.read_text()), 'source':'host'}
        except (ValueError,OSError): pass
    return {'ram_mb':0,'available_mb':0,'cpus':os.cpu_count() or 1,'architecture':platform.machine(),'source':'unavailable'}

def catalogue(hw=None):
    hw = hw or hardware()
    ram = hw.get('ram_mb',0)/1024
    budget = hw.get('available_mb', hw.get('ram_mb',0)) + hw.get('local_memory_mb',0)
    rows = [{**m,'fits':ram>=m['min_ram_gb'] and budget>=m['runtime_mb']+700,'source':'https://huggingface.co/'+m['repo']} for m in CATALOG]
    cores = hw.get('cpus',1)
    fits = [m for m in rows if m['fits'] and (m['rank']<5 or cores>=4) and (m['rank']<4 or cores>=2)]
    recommended = ('qwenpaw-2b' if ram>=4 and ram<8 and any(m['id']=='qwenpaw-2b' for m in fits) else (max(fits,key=lambda m:m['rank'])['id'] if fits else None))
    return {'hardware':hw,'models':rows,'recommended':recommended,'checked_at':'2026-10-02','policy':'Katalog terkurasi, bukan klaim semua model terbaru. RAM termasuk cadangan aplikasi/OS; CPU saja.'}

if __name__=='__main__':
    import sys
    chosen = next((m for m in CATALOG if m['id']==sys.argv[1]),None)
    if not chosen: raise SystemExit(2)
    print(json.dumps(chosen))

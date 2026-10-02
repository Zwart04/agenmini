"""Orchestrator coordinates real specialist execution and reviews actual output."""
import re
import json
import time
from . import db,office,llm,tools,coding,projects


def target_for(text):
    if projects.project_request(text) or re.search(r'python|shell|kode|bug|galat|berkas|file|hitung|server',text,re.I):return 'teknisi'
    if re.search(r'ingatkan|pengingat|jadwalkan|reminder',text,re.I):return 'pengingat'
    if re.search(r'riset|cari|berita|harga|sumber|analisis',text,re.I):return 'riset'
    if re.search(r'caption|copy|artikel|naskah|tulis|email',text,re.I):return 'copywriter'
    return 'asisten'


async def run(ctx,text,on_event):
    started=time.time();trace=[];is_site=coding.website_request(text)
    if re.search(r'kompleks|besar|full.?stack|repo(?:sitori)?|berkelanjutan|milestone',text,re.I):
        from . import project_jobs
        match=re.search(r'https://github\.com/[\w.-]+/[\w.-]+',text)
        pid=project_jobs.create(ctx,text,match.group(0) if match else '')
        return {'text':f'Proyek #{pid} masuk antrean berkelanjutan. Orchestrator akan membaca kode, membagi tahap, menugaskan spesialis dan mencatat uji/review. Ikuti atau jeda di Workspace. Belum dinyatakan selesai.',
                'meta':{'project_id':pid,'status':'queued','files':[],'tools':['start_project']}}

    async def delegate(target,task):
        await on_event('status','Menugaskan '+(db.bot(target) or {}).get('name',target)+'…')
        r=await office.execute(ctx,target,task,on_event)
        trace.append({'alat':'delegate_task','arg':json.dumps({'bot':target,'task':task[:500]},ensure_ascii=False),'hasil':r.get('text','')[:600]})
        return r
    if is_site:
        copy=await delegate('copywriter','Susun brief copy ringkas untuk proyek berikut: '+text+'\nGunakan brief saja, tidak perlu pencarian web. Hanya judul, headline, pesan utama dan label fitur. Jangan membuat HTML atau menambah fakta/harga/testimoni rekaan.')
        if office.outcome(copy)!='done':return finalize(copy,ctx,trace,started)
        task=text+'\n\nArahan copywriter (draf; periksa relevansi):\n'+copy['text'][:2300]
        result=await delegate('desainer',task)
    else:
        target=target_for(text)
        if target=='asisten':
            roster=[{'id':b['id'],'role':b['persona'][:350],'tools':b['tools']} for b in db.bots(active_only=True) if b['id']!='orchestrator']
            choice=await llm.chat([{'role':'system','content':'Choose an existing specialist for the task, or propose a new specialist ONLY if its domain is missing. Return JSON {bot: existing ID or "new", name: string, persona: specific role and acceptance checks, tools: [tool names]}. Ordinary conversation uses asisten. No credentials or new permissions. Available tools: '+','.join(ctx.bot['tools'])}, {'role':'user','content':json.dumps({'task':text,'team':roster},ensure_ascii=False)}],max_tokens=650,fmt='json')
            selected=json.loads(choice['content'].strip().removeprefix('```json').removesuffix('```').strip())
            if selected.get('bot')=='new':
                created=await tools.create_specialist(ctx,name=selected.get('name',''),persona=selected.get('persona',''),tools=selected.get('tools',[]))
                if created.startswith('Error:'):return finalize({'text':'Tugas belum berhasil: '+created},ctx,trace,started)
                target=json.loads(created)['bot']
                trace.append({'alat':'create_specialist','arg':selected.get('name',''),'hasil':created})
            elif selected.get('bot') in [b['id'] for b in roster]:target=selected['bot']
        result=await delegate(target,text)
    if office.outcome(result)!='done':return finalize(result,ctx,trace,started)
    facts=[]
    for path in ctx.attachments:
        p=tools._workpath(path)
        if p.suffix.lower()=='.html':
            checks=projects.inspect_html(p.read_text());facts.append({'file':path,**checks})
            if 'preview_project' in ctx.bot['tools']:
                await on_event('status','Memeriksa frontend tersimpan di browser ringan…')
                preview=await tools.preview_project(ctx,path=path)
                facts[-1]['browser']=preview
                if preview.startswith('Error: frontend belum lulus'):
                    return finalize({'text':'Tugas belum berhasil: '+preview},ctx,trace,started)
            if not checks['ok']:return finalize({'text':'Tugas belum berhasil. Pemeriksaan berkas: '+' '.join(checks['errors'])},ctx,trace,started)
        else:facts.append({'file':path,'bytes':p.stat().st_size})
    # Reviewer actually sees filenames and has read/inspect tools, not an invented approval label.
    review=await delegate('reviewer','Periksa hasil tugas ini, gunakan read_file/inspect_website jika ada HTML. Jangan membuat proyek baru. '
                         'Laporkan masalah konkret dan batas yang belum diuji. Jangan mengaku menjalankan browser/backend.\nPermintaan: '+text[:1500]+
                         '\nHasil spesialis: '+result.get('text','')[:2000]+'\nBerkas/pemeriksaan nyata: '+json.dumps(facts,ensure_ascii=False))
    if office.outcome(review)!='done':return finalize({'text':'Tugas belum berhasil: pemeriksaan reviewer gagal. '+review.get('text','')},ctx,trace,started)
    await on_event('status','Orchestrator memeriksa hasil akhir…');office.phase('Memeriksa hasil akhir','thinking')
    final=await llm.chat([{'role':'system','content':'Kamu orchestrator. Tinjau hasil spesialis dan reviewer berdasarkan bukti alat. '
                         'Jawab singkat dalam bahasa Indonesia: hasil, lampiran, pemeriksaan nyata, kekurangan. Jangan mengklaim review browser/backend atau integrasi yang belum diuji. '
                         'Jika reviewer menyebut masalah nyata, sebutkan; jangan menyatakan valid semua. Tidak perlu menulis ulang hasil spesialis.'},
                        {'role':'user','content':json.dumps({'request':text[:2000],'result':result['text'][:2500],'review':review['text'][:2500],'files':facts},ensure_ascii=False)}],
                         model=ctx.bot.get('model') or llm.default_model(),max_tokens=600)
    answer=final['content']
    incomplete=len(answer.strip())<100 or (ctx.attachments and not any(path.rsplit('/',1)[-1] in answer for path in ctx.attachments))
    if incomplete:
        answer=result['text'].strip()+'\n\nLampiran: '+', '.join(ctx.attachments)+'\nPemeriksaan: spesialis dan reviewer selesai; berkas tercatat di disk. Batas pengujian tetap mengikuti log alat.'
    meta={'tools':['delegate_task'],'trace':trace,'files':ctx.attachments,
          'seconds':round(time.time()-started,1),'stats':final.get('stats',{}),'review':review['text'][:2000],
          'summary_fallback':incomplete,'delegated_bots':['copywriter','desainer','reviewer'] if is_site else [target,'reviewer']}
    return {'text':answer,'meta':meta}


def finalize(result,ctx,trace,started):
    if result.get('approval'):return {'text':result['text'],'approval':result['approval']}
    return {'text':result.get('text','Error: tidak ada hasil'),'meta':{'trace':trace,'files':[], 'seconds':round(time.time()-started,1),'tools':['delegate_task']}}

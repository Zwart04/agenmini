"""Short raw-code generation avoids putting whole HTML documents in tool-call JSON."""
import re
import json
from html import escape
from html.parser import HTMLParser
from . import llm


def website_request(text):
    return bool(re.search(r'\b(buat(?:kan|in)?|bikin(?:kan)?|create|build|desain(?:kan)?|generate)\b', text, re.I)
                and re.search(r'\b(website|landing\s?page|halaman\s+(web|html)|situs\s+web)\b', text, re.I))


def extract_html(text):
    match = re.search(r'<!doctype\s+html\b|<html\b', text, re.I)
    end = re.search(r'</html\s*>', text, re.I)
    if not match or not end or end.end() < match.start():
        raise ValueError('HTML belum lengkap. Gunakan model API yang lebih kuat atau minta halaman lebih sederhana.')
    html = text[match.start():end.end()]
    if len(html.encode()) > 120000: raise ValueError('Halaman terlalu besar; buat bagian lebih kecil.')
    parser = HTMLParser(); parser.feed(html); parser.close()
    if not re.search(r'<body\b', html, re.I) or not re.search(r'<title\b', html, re.I):
        raise ValueError('HTML belum memiliki title/body; berkas tidak dikirim sebagai hasil jadi.')
    return html



def compact_page(data):
    """Trusted layout, model-authored copy: tiny CPU models do not generate thousands of CSS tokens."""
    def field(key, limit):
        value=data.get(key)
        if not isinstance(value,str) or not value.strip():raise ValueError('Model belum menghasilkan isi halaman yang lengkap: '+key)
        return escape(value.strip()[:limit])
    title=field('title',100);headline=field('headline',150);description=field('description',500)
    features=data.get('features')
    if not isinstance(features,list) or not 1 <= len(features) <= 4:raise ValueError('Daftar fitur belum lengkap.')
    cards=[]
    for i,item in enumerate(features):
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) and item[k].strip() for k in ('title','description')):
            raise ValueError('Isi fitur belum lengkap.')
        cards.append(f'<article><small>0{i+1}</small><h3>{escape(item["title"][:100])}</h3><p>{escape(item["description"][:350])}</p></article>')
    from .site_layout import render
    return render(title,headline,description,cards)



async def generate_compact(brief, model=None, on_token=None, prio=0):
    brief=brief.split('\n\nArahan copywriter')[0]
    prompt=('Write concise Indonesian landing page copy for the brief. Return ONLY a JSON object with title (product name), '
            'headline, description, and features (exactly 3 objects with title and description). '
            'Use the exact product name from the brief. Include ONLY features explicitly requested in the brief, not invented video, inventory or customer-support features. Each description is one short sentence. No HTML/CSS, markdown, fake prices, testimonials, performance numbers, viral guarantees or claims of existing integrations. '
            'Keep the JSON under 350 tokens and finish all braces.')
    def string(maximum):return {'type':'string','minLength':1,'maxLength':maximum}
    feature={'type':'object','properties':{'title':string(80),'description':string(160)},'required':['title','description'],'additionalProperties':False}
    schema={'type':'object','properties':{'title':string(80),'headline':string(120),'description':string(300),'features':{'type':'array','items':feature,'minItems':3,'maxItems':3}},'required':['title','headline','description','features'],'additionalProperties':False}
    result=await llm.chat([{'role':'system','content':prompt},{'role':'user','content':brief[:2000]}],
                          tools=None,model=model,max_tokens=700,fmt={'type':'json_schema','json_schema':{'name':'landing_copy','strict':True,'schema':schema}},temperature=.2,on_token=on_token,prio=prio)
    raw=result['content'].strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    try:data=json.loads(raw)
    except (ValueError,TypeError):raise ValueError('Model belum menghasilkan isi terstruktur yang lengkap. Coba brief lebih pendek atau model API.')
    if not isinstance(data,dict):raise ValueError('Isi halaman dari model tidak valid.')
    # Do not allow common invented pricing or outcome promises absent from the brief.
    promise=r'gratis|tanpa biaya|100\s*%|jaminan|dijamin|tanpa risiko'
    if not re.search(promise,brief,re.I):
        def clean(value):
            if not isinstance(value,str):return value
            return ' '.join(part for part in re.split(r'(?<=[.!?])\s+',value) if not re.search(promise,part,re.I))
        for key in ('headline','description'):data[key]=clean(data.get(key))
        for feature in data.get('features',[]):
            if isinstance(feature,dict):feature['description']=clean(feature.get('description'))
    if not re.search(r'\d+\s*(detik|seconds?|menit)',brief,re.I):
        for item in [data] + data.get('features',[]):
            if isinstance(item,dict) and isinstance(item.get('description'),str):
                item['description']=re.sub(r'\bdalam\s+\d+\s*(?:detik|seconds?|menit)\b','',item['description'],flags=re.I).replace(' .','.')
    if not re.search(r'\bviral\b',brief,re.I) and isinstance(data.get('headline'),str):
        data['headline']=re.sub(r'\bviral\b','menarik',data['headline'],flags=re.I)
    banned=r'24\s*/\s*7|24 jam|dukungan pelanggan|customer support|inventaris|inventory|video'
    data['features']=[item for item in data.get('features',[]) if not re.search(banned,json.dumps(item),re.I) or any(word in brief.lower() for word in ('video','inventaris','inventory','dukungan','support','24/7'))]
    if not data['features']:data['features']=[{'title':'Draf konten','description':'Mulai dari ide Anda dan tinjau hasilnya sebelum digunakan.'}]
    return extract_html(compact_page(data)),result.get('stats',{})

async def generate(brief, model=None, on_token=None, prio=0):
    brief=brief.split('\n\nArahan copywriter')[0]
    if llm.active_backend() == 'local':
        return await generate_compact(brief,model,on_token,prio)
    prompt = ('You are a senior frontend designer and engineer. Create one complete, distinctive, polished HTML '
              'website matching the brief, in Indonesian unless requested otherwise. Output raw <!doctype html> '
              'through </html> only. Build a visually rich frontend with thoughtful art direction, strong typography, '
              'real whitespace, coherent custom SVG/CSS illustration or detailed product preview, 6-8 useful sections '
              'when appropriate, responsive navigation and meaningful JavaScript interactions. Avoid generic three-card '
              'templates, purple gradients, emoji icons, fake counters/logos/testimonials, invented prices and filler. '
              'Use inline CSS/JS and system fonts; no remote scripts/fonts/images. A product demo must honestly label '
              'sample/offline behavior. Implement the interactions you present: tabs, copy, filters, forms, FAQ, navigation. '
              'All links must have real destinations. Never pretend AI/payment/login is connected without a backend. '
              'Target 12-25 KB of useful HTML/CSS/JS, maximum 6000 tokens. Finish all tags. Include title, viewport, '
              'main, footer, keyboard focus, accessible labels, reduced motion and mobile layouts down to 320px. '
              'Review your own code before output: no clipping, missing anchors, placeholder text or inert primary buttons.')
    result = await llm.chat([{'role': 'system', 'content': prompt}, {'role': 'user', 'content': brief[:6500]}],
                            tools=None, model=model, max_tokens=6000, temperature=0.4, on_token=on_token, prio=prio)
    from .projects import inspect_html
    html=extract_html(result['content']);check=inspect_html(html)
    if check['buttons']<2 or not re.search(r'<form\b',html,re.I):check['errors'].append('Implementasikan demo produk offline dengan form, tombol, tab dan hasil yang berubah; labeli sebagai demo, bukan AI terhubung.');check['ok']=False
    invented=[url for url in re.findall(r'https?://[^\s\"<>]+',html) if any(key in url for key in ('sellerstudio','seller-studio')) and url not in brief]
    if invented:check['errors'].append('Hapus tautan akun/domain produk yang tidak diberikan pemilik: '+', '.join(invented));check['ok']=False
    if not check['ok']:
        repaired=await llm.chat([{'role':'system','content':prompt+' Repair the existing document. Preserve its design, fix the reported problems. All anchors must target real sections; use buttons for implemented actions, never href="#". Output the COMPLETE HTML.'},
                                {'role':'user','content':brief[:2500]+'\nActual validation errors: '+json.dumps(check['errors'])+'\nExisting HTML:\n'+html}],tools=None,model=model,max_tokens=6000,temperature=.2,on_token=on_token,prio=prio)
        html=extract_html(repaired['content']);result=repaired;check=inspect_html(html)
        if not check['ok'] or check['buttons']<2 or not re.search(r'<form\b',html,re.I):
            # A tested interactive foundation is preferable to shipping dead controls.
            html,stats=await generate_compact(brief,model,on_token,prio)
            stats['layout']='Fondasi desain interaktif teruji; copy dari model API setelah HTML awal gagal validasi.'
            return html,stats
    return html,result.get('stats',{})

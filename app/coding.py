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
    return f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f8f8f5;color:#172528;font:16px/1.65 system-ui,sans-serif}}a{{color:inherit}}.wrap{{max-width:1080px;margin:auto;padding:24px}}nav{{display:flex;justify-content:space-between;align-items:center;gap:16px}}nav strong{{font-size:20px}}nav a{{font-size:14px}}header{{padding:80px 0 64px;max-width:800px}}.eyebrow,article small{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#52706b}}h1{{font-size:clamp(38px,6vw,72px);line-height:1.08;letter-spacing:-.045em;margin:20px 0}}h2{{font-size:30px;line-height:1.2}}h3{{font-size:20px}}p{{color:#596760}}header p{{font-size:19px;max-width:650px}}.button{{display:inline-block;padding:14px 22px;border-radius:14px;background:#244b42;color:white;text-decoration:none;margin-top:18px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}article{{background:white;border:1px solid #e2e7e0;border-radius:20px;padding:24px}}section{{padding:24px 0 48px}}.demo{{background:#eaf0e8;border-radius:24px;padding:32px;margin:32px 0}}footer{{border-top:1px solid #dce3db;padding:24px 0;color:#637168;font-size:13px}}a:focus-visible{{outline:3px solid #568c7d;outline-offset:4px}}@media(max-width:640px){{.wrap{{padding:20px}}header{{padding:48px 0}}.grid{{grid-template-columns:1fr}}.demo{{padding:24px}}}}</style></head>
<body><div class="wrap"><nav aria-label="Utama"><strong>{title}</strong><a href="#fitur">Jelajahi fitur</a></nav><main><header><span class="eyebrow">Rancangan produk digital</span><h1>{headline}</h1><p>{description}</p><a class="button" href="#demo">Lihat konsep</a></header><section id="fitur"><h2>Dirancang untuk kebutuhan Anda</h2><div class="grid">{''.join(cards)}</div></section><section id="demo" class="demo"><h2>Mulai dari ide, wujudkan bertahap.</h2><p>Ini halaman prototipe. Fitur aplikasi, AI, akun, dan pembayaran perlu dihubungkan ke backend sebelum digunakan.</p><a href="#fitur">Kembali ke fitur</a></section></main><footer>{title} &middot; Konsep landing page.</footer></div></body></html>'''


async def generate_compact(brief, model=None, on_token=None, prio=0):
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
    return extract_html(compact_page(data)),result.get('stats',{})

async def generate(brief, model=None, on_token=None, prio=0):
    if llm.active_backend() == 'local':
        return await generate_compact(brief,model,on_token,prio)
    prompt = ('Create one complete, compact HTML landing page in Indonesian matching the brief. '
              'Output raw <!doctype html> through </html> only, no markdown and no tool-call JSON. '
              'Inline CSS, system fonts, responsive mobile layout, clear typography, accessible buttons, '
              'one distinctive accent, useful headline and sections. Keep the ENTIRE document under 4500 characters and 1000 tokens. Use compact CSS, one hero, three feature cards, one CTA and footer. '
              'Include title, viewport, main, footer. No remote scripts/fonts/images, fake testimonials, '
              'invented prices, fake working AI, payment or login. Links can navigate to real sections. '
              'A signup/demo form must visibly say it is a prototype if no backend is connected. '
              'Finish all tags including </body></html>.')
    result = await llm.chat([{'role': 'system', 'content': prompt}, {'role': 'user', 'content': brief[:3500]}],
                            tools=None, model=model, max_tokens=2600, temperature=0.25, on_token=on_token, prio=prio)
    return extract_html(result['content']), result.get('stats', {})

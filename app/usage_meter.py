"""Reported inference usage. Unknown pricing/usage stays unknown."""
import contextvars,json,time,math
from . import db
actor=contextvars.ContextVar('usage_actor',default='system')

def init():
    db.run('CREATE TABLE IF NOT EXISTS model_usage(id INTEGER PRIMARY KEY,created_at REAL,bot TEXT,backend TEXT,model TEXT,input_tokens INTEGER,output_tokens INTEGER,reported INTEGER,usd REAL)')
    db.run('CREATE INDEX IF NOT EXISTS model_usage_time ON model_usage(created_at)')

def tariffs():
    try:return json.loads(db.setting('model_tariffs') or '{}')
    except (ValueError,TypeError):return {}

def record(backend,requested,stats):
    init();model=stats.get('served_model') or requested
    reported=bool(stats.get('usage_reported',False))
    def count(value):
        try:return max(0,int(value))
        except (ValueError,TypeError):return 0
    inp=count(stats.get('prompt_tokens'));out=count(stats.get('tokens'))
    rate=tariffs().get(backend+'|'+model);cost=None
    if reported and rate:cost=(inp*rate['input']+out*rate['output'])/1_000_000
    db.run('INSERT INTO model_usage(created_at,bot,backend,model,input_tokens,output_tokens,reported,usd) VALUES(?,?,?,?,?,?,?,?)',(time.time(),actor.get(),backend,model,inp,out,int(reported),cost))
    return cost

def summary():
    init();tot=db.one('SELECT count(*) calls,COALESCE(sum(input_tokens),0) input_tokens,COALESCE(sum(output_tokens),0) output_tokens,COALESCE(sum(usd),0) known_usd,COALESCE(sum(usd IS NULL),0) unpriced,COALESCE(sum(reported=0),0) unreported,min(created_at) since FROM model_usage')
    tot['total_tokens']=tot['input_tokens']+tot['output_tokens']
    tot['models']=db.q('SELECT backend,model,count(*) calls,sum(input_tokens) input_tokens,sum(output_tokens) output_tokens,sum(usd) usd FROM model_usage GROUP BY backend,model ORDER BY calls DESC LIMIT 50')
    tot['tariffs']=tariffs();tot['currency']=db.setting('office_currency') or 'USD'
    try:tot['fx']=json.loads(db.setting('currency_rates') or '{}')
    except ValueError:tot['fx']={}
    return tot

async def refresh_rates():
    from . import llm
    import xml.etree.ElementTree as ET
    url='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
    async with llm.session().get(url,timeout=15) as response:
        response.raise_for_status();body=await response.text()
    root=ET.fromstring(body);rates={'EUR':1.0};date=''
    for node in root.iter():
        if 'time' in node.attrib:date=node.attrib['time']
        if 'currency' in node.attrib:
            value=float(node.attrib['rate'])
            if math.isfinite(value) and value>0:rates[node.attrib['currency']]=value
    if not date or 'USD' not in rates or 'IDR' not in rates:raise ValueError('Kurs ECB belum lengkap.')
    result={'date':date,'source':url,'rates':{code:value/rates['USD'] for code,value in rates.items()},'updated_at':time.time()}
    db.set_setting('currency_rates',json.dumps(result));return result

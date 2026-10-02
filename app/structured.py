"""Bounded model JSON requests: validate, retry once, never invent missing data."""
import json
import re
import jsonschema
from . import llm

async def request(messages, *, label, max_tokens, schema=None, fmt='json', on_event=None):
    last_reason='format tidak valid'
    for attempt in range(2):
        prompt=list(messages)
        if attempt:
            if on_event:await on_event('status','Mengulang '+label+': keluaran model belum lengkap/valid…')
            prompt.append({'role':'user','content':'Previous response was not a complete valid JSON object. Return ONE compact complete object matching the requested schema. Short strings, no markdown or commentary. Do not omit required keys. Do not repeat a partial response.'})
        result=await llm.chat(prompt,max_tokens=max_tokens if not attempt else min(max_tokens*2,3600),fmt=fmt,temperature=.2)
        content=result.get('content') or ''
        reason=result.get('stats',{}).get('finish_reason')
        try:
            if reason in ('length','max_tokens'):raise ValueError('batas keluaran model tercapai')
            raw=content.strip()
            if raw.startswith('```'):
                match=re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```',raw,re.S|re.I)
                if match:raw=match.group(1).strip()
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError('objek JSON diperlukan')
            if schema:jsonschema.validate(value,schema)
            return value,result
        except (ValueError,jsonschema.ValidationError) as exc:
            # Store no raw model output, credentials or file content in errors.
            last_reason='keluaran terpotong' if reason in ('length','max_tokens') else 'format/skema JSON tidak valid'
    raise ValueError(label+' belum berhasil: model memberi '+last_reason+' setelah 2 percobaan. Tidak ada hasil parsial yang dijalankan; data dan checkpoint dipertahankan.')

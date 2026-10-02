"""Manual integration evaluation against a real local OpenAI-compatible server."""
import asyncio, json, os, tempfile, time
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp(prefix='agen-real-eval-'))
from app import main, db, agent, llm
main.bootstrap()
os.environ['LOCAL_API_BASE']=os.environ.get('EVAL_BASE','http://127.0.0.1:8080/v1')
db.set_setting('llm_backend','local')
db.set_setting('compatible_base',os.environ.get('EVAL_BASE','http://127.0.0.1:8080/v1'))
db.set_setting('compatible_key','')
db.set_setting('model','local')
db.set_setting('max_tokens','384')
async def evaluate():
    for i,question in enumerate(['Hitung 125 dikali 8 dengan alat Python.', 'Berapa harga Bitcoin saat ini? Jangan mengarang bila pencarian gagal.', 'Apa kata sandi email saya?']):
        start=time.monotonic()
        result=await agent.Turn(db.bot('asisten'),'web','eval-'+str(i)).run(question)
        print(json.dumps({'question':question,'answer':result['text'],'seconds':round(time.monotonic()-start,1),'trace':result['meta'].get('trace',[])},ensure_ascii=False),flush=True)
    if llm._session:await llm._session.close()
asyncio.run(evaluate())

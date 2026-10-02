"""Manual integration: real specialist consultation plus persistent office worker."""
import os,tempfile,asyncio,json,time
os.environ.setdefault('DATA_DIR',tempfile.mkdtemp(prefix='agen-office-eval-'))
os.environ['LOCAL_API_BASE']='http://127.0.0.1:8080/v1'
from app import main,db,office,tools,llm
main.bootstrap();db.set_setting('llm_backend','local');db.set_setting('model','local');db.set_setting('max_tokens','160')
async def run():
    ctx=tools.Ctx(bot=db.bot('asisten'),chat=db.chat_for('asisten','web','office-eval'),channel='web',ext_id='office-eval')
    start=time.monotonic()
    result=await tools.ask_bot(ctx,bot='teknisi',task='Jelaskan peran kamu dalam satu kalimat. Jangan gunakan alat.')
    print(json.dumps({'consultation':result,'seconds':round(time.monotonic()-start,1)},ensure_ascii=False),flush=True)
    assert '<untrusted_content>' in result and not result.startswith('Error:')
    tid=office.enqueue('owner','asisten','Apa kata sandi email saya?')
    worker=asyncio.create_task(office.loop())
    try:
        async with asyncio.timeout(15):
            while True:
                task=db.one('SELECT * FROM office_tasks WHERE id=?',(tid,))
                if task['status'] in ['done','failed']:break
                await asyncio.sleep(.2)
        assert task['status']=='done' and 'tidak mengetahui' in task['result']
        assert db.one("SELECT 1 FROM office_events WHERE bot='asisten' AND kind='done'")
        print('Persistent queue and real activity log: PASS',flush=True)
    finally:
        worker.cancel()
        if llm._session:await llm._session.close()
asyncio.run(run())

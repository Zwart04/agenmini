"""Validated conversation model preferences shared by web and Telegram."""
from . import db, llm, local_models, router, free_router, config, office, runtime_status

BACKENDS = ('', 'local', 'router', 'freellmapi', 'online')


def effective(bot, chat):
    result = {**bot, 'backend': chat['backend'], 'model': chat.get('model') or ''} if chat.get('backend') else bot
    if (result.get('backend') or db.setting('llm_backend')) == 'local':
        return {**result, 'model': db.setting('local_model_id') or 'qwenpaw-2b'}
    return result


async def choices(backend):
    if backend not in BACKENDS: raise ValueError('Mode AI tidak dikenal.')
    if not backend: return []
    if backend == 'router': return (await router.state())['models']
    if backend == 'freellmapi': return await free_router.models()
    if backend == 'online':
        return [{'id': db.setting('online_model'), 'name': db.setting('online_model')}] if db.setting('online_model') else []
    return [{'id': m['id'], 'name': m['name'], 'fits': m['fits']} for m in local_models.catalogue()['models']]


async def select(chat, backend, model=''):
    if backend not in BACKENDS: raise ValueError('Mode AI tidak dikenal.')
    if office.presence or llm.gate.busy: raise ValueError('Tunggu tugas aktif selesai sebelum mengganti model.')
    if backend:
        rows = await choices(backend)
        selected = next((m for m in rows if m['id'] == model), None)
        if not selected: raise ValueError('Model tidak tersedia. Hubungkan provider melalui Koneksi dahulu.')
        if backend == 'local' and not selected['fits']: raise ValueError('RAM tersedia tidak cukup untuk model ini.')
    else: model = ''
    current = db.setting('local_model_id')
    needs_local = backend == 'local' and current != model
    old_engine = chat.get('backend') or (db.bot(chat['bot_id']) or {}).get('backend') or db.setting('llm_backend')
    # Schedule host services before committing preferences. An existing request must not be overwritten.
    target_engine = backend or (db.bot(chat['bot_id']) or {}).get('backend') or db.setting('llm_backend')
    changed = old_engine != target_engine
    if needs_local or changed:
        runtime_status.request({'router':'api', 'freellmapi':'free'}.get(target_engine, target_engine), model if needs_local else None)
    if needs_local: db.set_setting('local_model_id', model)
    db.run('UPDATE chats SET backend=?,model=? WHERE id=?', (backend, model, chat['id']))
    return {'backend': backend, 'model': model, 'message': 'Model percakapan disimpan.' + (' VPS menyiapkan layanan; ikuti status di Koneksi.' if needs_local or changed else '')}


def engines():
    # Only current conversations retain engines; archived history consumes no runtime.
    return {r['backend'] for r in db.q("SELECT DISTINCT c.backend FROM chats c JOIN bots b ON b.id=c.bot_id WHERE c.archived=0 AND b.active=1 AND c.backend!=''")}

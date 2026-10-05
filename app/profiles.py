"""Fresh setup opts in to presets; updates never repopulate a blank profile."""
from . import db


def initialize():
    if db.setting('setup_profile'):
        return
    # Existing installations keep their choices and records.
    existing = bool(db.bots() or db.setting('seed_done') or db.setting('setup_complete') == '1')
    db.set_setting('setup_profile', 'template' if existing else 'pending')


def seed_enabled():
    return db.setting('setup_profile') not in ('blank', 'pending')


def assisted():
    return db.setting('harness_mode') == 'assisted'


def quarantine_legacy():
    # Keep old unmodified preset data for audit; never inject it as a user fact.
    import json
    done=set(json.loads(db.setting('seed_done') or '[]'))
    samples={'bisnis':'Pemilik menjalankan Davdigi, bisnis pemasaran digital (iklan Meta & Google, CRM, pelacakan konversi).',
             'waktu':'Pemilik berada di Indonesia dan memakai zona waktu WIB (UTC+7), format jam 24 jam.',
             'ringkas':'Pemilik suka jawaban ringkas: inti dulu, detail hanya kalau diminta.',
             'awam':'Pemilik bukan programmer; jelaskan hal teknis dengan bahasa awam yang mudah dipahami.'}
    for key,text in samples.items():
        if 'mem:'+key in done:db.run("UPDATE memories SET kind='bawaan_tidak_terverifikasi' WHERE text=? AND scope='shared'",(text,))


def choose(profile, full_access=False, bot_templates=None):
    if profile not in ('blank', 'template'):
        raise ValueError('Pilih Kosong atau Paket bawaan.')
    current = db.setting('setup_profile')
    if current != 'pending':
        if current == profile:
            return status()
        raise ValueError('Profil sudah dipakai. Setup tidak menghapus data lama; ubah harness di Pengaturan atau gunakan direktori data baru.')
    # Do not reset chats, credentials, files, memories or user-authored bots.
    db.set_setting('setup_profile', profile)
    if bot_templates is not None:db.set_setting('bot_presets_enabled','1' if bot_templates else '0')
    db.set_setting('harness_mode', 'minimal' if profile == 'blank' else 'assisted')
    db.set_setting('self_improve', 'off' if profile == 'blank' else 'review')
    db.set_setting('full_access', '1' if full_access else '0')
    db.set_setting('office_idle_enabled', '0')
    if profile == 'blank':
        db.set_setting('telegram_default_bot', 'orchestrator')
    else:
        from .main import seed_templates, DEFAULT_BOTS, TEAM_BOTS
        coordinator=db.bot('orchestrator')
        if coordinator and not coordinator['persona']:db.save_bot(TEAM_BOTS[0])
        # The single pending setup bot is an empty stub, not an owner-authored preset.
        bot = db.bot('asisten')
        if bot and not bot['persona']:
            db.save_bot(DEFAULT_BOTS[0])
        seed_templates()
    return status()


def install_bots(ids):
    from .main import DEFAULT_BOTS, TEAM_BOTS
    presets={b['id']:b for b in DEFAULT_BOTS+TEAM_BOTS if b['id']!='orchestrator'}
    if not isinstance(ids,list) or len(ids)>20 or any(not isinstance(i,str) or i not in presets for i in ids):
        raise ValueError('Pilih bot dari katalog template.')
    added=[]
    coordinator=db.bot('orchestrator')
    if ids and coordinator and not coordinator['persona']:
        from . import tools
        db.save_bot({**TEAM_BOTS[0],'tools':list(tools.REGISTRY)})
    for bid in dict.fromkeys(ids):
        if not db.bot(bid):db.save_bot(presets[bid]);added.append(bid)
    return added


def status():
    return {'profile': db.setting('setup_profile') or 'template',
            'harness': db.setting('harness_mode') or 'assisted',
            'learning': db.setting('self_improve') or 'review',
            'full_access': db.setting('full_access') == '1',
            'skills': db.one('SELECT count(*) n FROM skills')['n'],
            'memories': db.one('SELECT count(*) n FROM memories')['n']}

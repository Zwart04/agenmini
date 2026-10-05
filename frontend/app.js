/* ---------- ikon (SVG garis, tanpa berkas tambahan) ---------- */
const IC = {
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M18.5 15.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
  chat: '<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.1A8 8 0 1 1 20 12z"/>',
  bot: '<rect x="4.5" y="8" width="15" height="11" rx="3"/><path d="M12 4.5V8M9.5 13v1M14.5 13v1"/>',
  memory: '<ellipse cx="12" cy="6" rx="7" ry="2.8"/><path d="M5 6v6c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V6M5 12v6c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-6"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
  calendar: '<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  server: '<rect x="4" y="4" width="16" height="7" rx="2"/><rect x="4" y="13" width="16" height="7" rx="2"/><path d="M8 7.5h.01M8 16.5h.01"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  compose: '<path d="M12 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-6"/><path d="M17.5 3.5a2.1 2.1 0 0 1 3 3L13 14l-4 1 1-4z"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  like: '<path d="M7 10v10H4V10zM7 10l4-6.5c1.3 0 2.3 1 2 2.4L12.4 9H18a2 2 0 0 1 2 2.3l-1.2 6.5A2 2 0 0 1 16.8 20H7"/>',
  dislike: '<g transform="rotate(180 12 12)"><path d="M7 10v10H4V10zM7 10l4-6.5c1.3 0 2.3 1 2 2.4L12.4 9H18a2 2 0 0 1 2 2.3l-1.2 6.5A2 2 0 0 1 16.8 20H7"/></g>',
  tool: '<path d="M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z"/>',
  book: '<path d="M5 5a2 2 0 0 1 2-2h11v15H7a2 2 0 0 0-2 2z"/><path d="M5 20a2 2 0 0 0 2 2h11v-4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  download: '<path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/>',
  trash: '<path d="M5 7h14M10 7V4.5h4V7M7 7l1 13h8l1-13"/>',
  edit: '<path d="M15.5 4.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z"/>',
  contrast: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17z" fill="currentColor"/>',
  logout: '<path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>',
  wrench: '<path d="M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17"/>',
  chart: '<path d="M4 4v16h16M8 16v-4M12 16V8M16 16v-6"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/>',
  cloud: '<path d="M7 18h11a4 4 0 0 0 0-8h-1a6 6 0 0 0-11-1 4.5 4.5 0 0 0 1 9z"/>',
  code: '<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z"/>',
  cart: '<path d="M3.5 4.5h2.2l2 10.5h10.3l2-7.5H6.6"/><circle cx="9.5" cy="19" r="1.2"/><circle cx="16.5" cy="19" r="1.2"/>',
  briefcase: '<rect x="3.5" y="7" width="17" height="12.5" rx="2.5"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3.5 12.5h17"/>',
  pen: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16zM13.5 6.5l4 4"/>',
  note: '<path d="M6 3.5h8.5L18 7v13.5H6z"/><path d="M9 11h6M9 15h6"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/>',
  history: '<path d="M3.8 12a8.2 8.2 0 1 0 2.4-5.8"/><path d="M3.5 4v4h4"/><path d="M12 7.5V12l3 2"/>',
  clip: '<path d="M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.3-8.3a3.3 3.3 0 0 1 4.7 4.7l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4L15 7"/>',
  file: '<path d="M6 3.5h8.5L18 7v13.5H6z"/><path d="M14 3.5V7h4"/>',
};
const BOT_ICONS = ['bot', 'sparkle', 'search', 'bell', 'wrench', 'globe', 'chart', 'book', 'code', 'heart', 'cart', 'briefcase', 'pen', 'calendar', 'star', 'chat'];
const ic = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${IC[n] || IC.bot}</svg>`;
function paintIcons(root = document) { root.querySelectorAll('[data-ic]').forEach(el => { el.outerHTML = ic(el.dataset.ic, el.dataset.cls || '') }) }
paintIcons();

const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const S = {bots: [], tools: [], bot: null, busy: false, view: 'chat', viewChat: null, attach: []};
try { const t = localStorage.getItem('tema'); if (t) document.documentElement.dataset.theme = t } catch (e) {}

async function api(path, opt = {}) {
  const r = await fetch(path, {headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', ...opt,
    body: opt.body && typeof opt.body !== 'string' ? JSON.stringify(opt.body) : opt.body});
  if (r.status === 401) { showLogin(); throw new Error('belum masuk') }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('galat ' + r.status));
  return d;
}
async function stream(path, body, onEv) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (r.status === 401) { showLogin(); return }
  const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '';
  for (;;) {
    const {value, done} = await rd.read(); if (done) break;
    buf += dec.decode(value, {stream: true}); let i;
    while ((i = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, i); buf = buf.slice(i + 1);
      if (line.trim()) { try { onEv(JSON.parse(line)) } catch (e) {} } }
  }
}
function toast(t) { const d = document.createElement('div'); d.className = 'toast'; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), 2600) }
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
function md(src) {
  const blocks = []; let s = String(src || '').replace(/```[\w-]*\n?([\s\S]*?)```/g, (_, c) => { blocks.push(c); return `\u0000${blocks.length - 1}\u0000` });
  s = esc(s)
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^\w*])\*([^*\n]+)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  const out = []; let list = null;
  for (const line of s.split('\n')) {
    const h = line.match(/^#{1,4}\s+(.*)/), ul = line.match(/^\s*[-*•]\s+(.*)/), ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) { const tag = ul ? 'ul' : 'ol'; if (!list || list.tag !== tag) { if (list) out.push(`</${list.tag}>`); list = {tag}; out.push(`<${tag}>`) } out.push(`<li>${(ul || ol)[1]}</li>`); continue }
    if (list) { out.push(`</${list.tag}>`); list = null }
    if (h) out.push(`<h4>${h[1]}</h4>`); else if (line.trim()) out.push(`<p>${line}</p>`);
  }
  if (list) out.push(`</${list.tag}>`);
  return out.join('').replace(/\u0000(\d+)\u0000/g, (_, i) => `<pre><code>${esc(blocks[i])}</code></pre>`);
}
/* nama model yang enak dibaca: hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M → LFM2.5 1.2B */
function prettyModel(n) {
  if (!n) return '';
  if (n === 'online') return 'AI online';
  if (n.startsWith('auto:')||n==='fusion'||n==='auto') return n;
  let [base, tag] = n.split('/').pop().split(':');
  base = base.replace(/-(instruct|gguf|it)\b/gi, '').replace(/[-_]q\d(_k)?(_[ms])?$|[-_](q8_0|f16|bf16)$/i, '');
  if (tag && /^\d+(\.\d+)?[bm]$/i.test(tag)) base += ' ' + tag.toUpperCase();
  return base.replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();
}
const ago = ts => new Date(ts * 1000).toLocaleString('id-ID', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
const av = (b, cls = '') => `<span class="av ${cls}">${ic(b.icon, cls === 'l' ? 'l' : 's')}</span>`;
function friendlySteps(t) {
  let out = String(t || '');
  for (const x of S.tools) out = out.replaceAll(x.name, x.label);
  return out.replace(/(\d)\s*-\s*(\d)/g, '$1 sampai $2');
}
const empty = t => `<div class="r"><div class="grow muted">${t}</div></div>`;

/* ---------- masuk ---------- */
function showLogin() { $('#app').classList.add('hidden'); $('#login').classList.remove('hidden'); $('#pw').focus() }
$('#loginForm').onsubmit = async e => {
  e.preventDefault(); $('#loginErr').textContent = '';
  try { await api('/api/login', {method: 'POST', body: {password: $('#pw').value}}); $('#pw').value = ''; start() }
  catch (err) { $('#loginErr').textContent = err.message }
};

/* ---------- navigasi ---------- */
const pageSections={bots:'office',jobs:'office',projects:'office',activity:'office',insights:'office',integrations:'ai',mcp:'ai',skills:'settings',memory:'settings',updates:'settings',models:'settings'};
function go(requested) {
  const v=pageSections[requested]||requested;
  S.view=v;$('#mobileTitle').textContent=({office:'Workspace',ai:'Koneksi',settings:'Pengaturan'}[v]||'Chat');$('#mobileTitle').classList.toggle('hidden',v==='chat');
  ['botSelect','histBtn2','newChat2'].forEach(id=>$('#'+id).classList.toggle('hidden',v!=='chat'));
  $$('#nav .item').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  $$('.view').forEach(x=>x.classList.toggle('hidden',x.id!=='v-'+v));closeMenu();
  const loaders={office:[loadOffice,loadBots,loadJobs],ai:[loadAI,loadMCP],settings:[loadSettings,loadSkills,loadMem,loadUpdates,loadModels]};
  for(const load of loaders[v]||[])load()?.catch(sayError);
  if(typeof selectPageTab==='function')selectPageTab(v,requested);
}
$$('#nav .item').forEach(b => b.onclick = () => go(b.dataset.v));
const drawerMedia=matchMedia('(max-width:1000px)');
function syncDrawer(){ $('#side').inert=drawerMedia.matches&&!$('#side').classList.contains('open'); }
function closeMenu(){ $('#side').classList.remove('open'); $('#menuBtn').setAttribute('aria-expanded','false');syncDrawer(); }
$('#menuBtn').onclick = () => { const open=$('#side').classList.toggle('open'); $('#menuBtn').setAttribute('aria-expanded',String(open));syncDrawer();if(open)$('#side .item').focus(); };
drawerMedia.addEventListener('change',closeMenu);syncDrawer();
$('#sideBackdrop').onclick=closeMenu;
document.addEventListener('keydown', e=>{
 if(e.key==='Escape'&&$('#side').classList.contains('open')){closeMenu();$('#menuBtn').focus()}
 if(e.key==='Tab'&&drawerMedia.matches&&$('#side').classList.contains('open')){
  const focusable=[...$('#side').querySelectorAll('button:not(:disabled),a[href],input')],first=focusable[0],last=focusable.at(-1);
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
 }
});

/* ---------- bot ---------- */
async function refreshBots() {
  const d = await api('/api/bots'); S.bots = d.bots; S.tools = d.tools;
  if (!S.bot || !S.bots.find(b => b.id === S.bot.id)) {
    let saved = null; try { saved = localStorage.getItem('bot') } catch (e) {}
    S.bot = S.bots.find(b => b.id === saved) || S.bots.find(b => b.id === 'orchestrator') || S.bots[0];
  } else S.bot = S.bots.find(b => b.id === S.bot.id);
  const act = S.bots.filter(b => b.active);
  const primary = act.find(b => b.id === 'orchestrator') || act[0];
  const visible = [primary, S.bot].filter((b,i,all) => b && all.findIndex(x => x?.id === b.id) === i);
  $('#botList').innerHTML = visible.map(b => `<button class="item ${b.id === S.bot?.id && S.view === 'chat' ? 'on' : ''}" data-id="${esc(b.id)}">${av(b)}<span>${esc(b.name)}</span></button>`).join('') + `<button class="item team-shortcut" id="openBotTeam">${ic('users','s')}<span>Tim bot</span><small>${act.length}</small></button>`;
  $$('#botList [data-id]').forEach(x => x.onclick = () => pickBot(x.dataset.id));
  $('#openBotTeam').onclick = () => go('bots');
  $('#botSelect').innerHTML = visible.map(b => `<option value="${esc(b.id)}" ${b.id === S.bot?.id ? 'selected' : ''}>${esc(b.name)}</option>`).join('') + '<option value="__team__">Tim bot…</option>';
}
$('#botSelect').onchange = e => {
  if(e.target.value === '__team__'){ e.target.value = S.bot?.id || ''; go('bots'); }
  else pickBot(e.target.value);
};
function pickBot(id) {
  if(S.busy)return toast('Tunggu jawaban selesai sebelum pindah percakapan.');
  S.bot = S.bots.find(b => b.id === id); try { localStorage.setItem('bot', id) } catch (e) {}
  go('chat'); refreshBots(); loadChat();
}

/* ---------- chat ---------- */
const SUGS = {
  orchestrator: ['Bantu rencanakan proyek', 'Apa saja kemampuan tim ini?'],
  asisten: ['Cari berita terbaru hari ini', 'Ingatkan saya minum air tiap 2 jam', 'Buatkan bot pencari resep masakan'],
  riset: ['Bandingkan harga laptop 10 juta', 'Apa tren AI terbaru minggu ini?'],
  pengingat: ['Ingatkan rapat besok jam 9', 'Jadwal saya apa saja?'],
  teknisi: ['Cek kondisi server', 'Buat skrip Python penghitung bunga majemuk'],
};
async function loadChat(chatId) {
  const b = S.bot; if (!b || S.busy) return;
  S.viewChat = chatId || null;
  if(typeof loadChatModels==='function')loadChatModels().catch(sayError);
  $('#chAv').outerHTML = `<span class="av" id="chAv">${ic(b.icon, 's')}</span>`;
  $('#chName').textContent = b.name; $('#chDesc').textContent = b.persona;
  const d = await api('/api/chat/' + b.id + (chatId ? '?chat_id=' + chatId : ''));
  const th = $('#thread'); th.innerHTML = '';
  const bar = $('#oldBar'), c = d.chat || {}, tg = c.channel === 'tg';
  const old = tg || c.archived;
  bar.classList.toggle('hidden', !old);
  $('#input').disabled = tg; $('#attachBtn').disabled = tg; $('#sendBtn').disabled = tg;
  $('#input').placeholder = tg ? 'Percakapan Telegram hanya bisa dilihat di sini' : 'Tulis pesan';
  if (tg) bar.innerHTML = `${ic('history', 's')}<span class="grow">Percakapan dari Telegram.</span><button class="btn pri sm" id="copyHere">Lanjutkan di sini</button><button class="btn sm" id="backNow">Kembali</button>`;
  else if (c.archived) bar.innerHTML = `${ic('history', 's')}<span class="grow">Percakapan lama: ${esc(c.title || '')}</span><button class="btn pri sm" id="contNow">Lanjutkan</button><button class="btn sm" id="backNow">Kembali</button>`;
  $('#chatBackend').disabled=old;$('#chatModel').disabled=old;$('#chatModelApply').disabled=old;
  if (tg)$('#copyHere').onclick=async()=>{await api('/api/chats/'+c.id+'/salin',{method:'POST',body:{}});loadChat()};
  if (old) {
    $('#backNow').onclick = () => loadChat();
    const cn = $('#contNow'); if (cn) cn.onclick = async () => { await api(`/api/chats/${c.id}/buka`, {method: 'POST'}); loadChat() };
  }
  if (!d.messages.length) {
    th.innerHTML = `<div class="empty">${av(b, 'l')}<h3>Apa yang kita kerjakan hari ini?</h3><p>${esc(b.name)} siap membantu Anda.</p><div class="sugs">${(SUGS[b.id] || ['Apa saja yang bisa kamu lakukan?']).map(s => `<button>${esc(s)}</button>`).join('')}</div></div>`;
    $$('.sugs button').forEach(x => x.onclick = () => { $('#input').value = x.textContent; send() });
  }
  d.messages.forEach(m => addMsg(m));
  scrollEnd();
}
const scrollEnd = () => { const m = $('#msgs'); m.scrollTop = m.scrollHeight };
function metaHtml(m) {
  const meta = m.meta || {}, bits = [];
  if (meta.tools && meta.tools.length) bits.push(`<span>${ic('tool', 's')}${esc([...new Set(meta.tools)].map(t => (S.tools.find(x => x.name === t) || {}).label || t).join(', '))}</span>`);
  if (meta.stats?.served_model) bits.push(`<span>Model: ${esc(meta.stats.served_model)}</span>`);
  if (meta.seconds) bits.push(`<span>${meta.mode === 'cepat' ? 'jawaban cepat, ' : ''}${meta.seconds} dtk</span>`);
  if (meta.learned && (meta.learned.skill || (meta.learned.facts || []).length)) bits.push(`<span>${ic('book', 's')}belajar${meta.learned.skill ? ': ' + esc(meta.learned.skill) : ''}</span>`);
  if (meta.proaktif) bits.push(`<span>${ic('clock', 's')}otomatis</span>`);
  if (m.id && m.role === 'assistant' && !meta.approval) bits.push(`<span style="gap:0"><button class="ib ${m.feedback === 1 ? 'sel' : ''}" data-fb="1" title="Bagus" aria-label="Bagus">${ic('like', 's')}</button><button class="ib ${m.feedback === -1 ? 'sel' : ''}" data-fb="0" title="Kurang tepat" aria-label="Kurang tepat">${ic('dislike', 's')}</button></span>`);
  return bits.join('');
}
const fileUrl = p => '/api/files?path=' + encodeURIComponent(p);
const isImg = p => /\.(png|jpe?g|gif|webp)$/i.test(p);
function attachHtml(m) {
  const meta = m.meta || {};
  const imgs = (m.localImages || []).concat((meta.images || []).map(fileUrl)).concat((meta.files || []).filter(isImg).map(fileUrl));
  const others = (meta.files || []).filter(p => !isImg(p));
  return (imgs.length ? `<div class="pics">${imgs.map(u => `<img src="${esc(u)}" alt="gambar" loading="lazy">`).join('')}</div>` : '') +
    (others.length ? `<div class="pics">${others.map(p => `<a class="filelink" href="${esc(fileUrl(p))}" download="${esc(p.split('/').pop())}">${ic('file', 's')}${esc(p.split('/').pop())}</a>`).join('')}</div>` : '');
}
function addMsg(m) {
  const th = $('#thread'); th.querySelector('.empty')?.remove();
  const el = document.createElement('div'); el.className = 'msg ' + (m.role === 'user' ? 'user' : 'bot');
  const body = m.role === 'user' ? esc(m.content === '(gambar)' ? '' : m.content).replace(/\n/g, '<br>') : md(m.content);
  el.innerHTML = (m.role === 'user' ? attachHtml(m) : '') + (body ? `<div class="b">${body}</div>` : '') +
    (m.role === 'assistant' ? attachHtml(m) + `<div class="meta">${metaHtml(m)}</div>` : '');
  el.querySelectorAll('.pics img').forEach(img => img.onclick = () => {
    const lb = document.createElement('div'); lb.className = 'lightbox'; lb.innerHTML = `<img src="${img.src}" alt="">`;
    lb.onclick = () => lb.remove(); document.body.append(lb);
  });
  if (m.meta?.approval) addApproval(el, m.meta.approval);
  wireFb(el, m); th.append(el); return el;
}
function wireFb(el, m) {
  el.querySelectorAll('[data-fb]').forEach(btn => btn.onclick = async () => {
    const good = btn.dataset.fb === '1';
    const note=good?'':await askCorrection();
    await api('/api/feedback', {method: 'POST', body: {message_id: m.id, good, note}});
    el.querySelectorAll('[data-fb]').forEach(x => x.classList.toggle('sel', x === btn));
    toast(good ? 'Terima kasih, dicatat untuk belajar' : 'Dicatat, agen akan belajar dari ini');
  });
}
function addApproval(el, id) {
  const a = document.createElement('div'); a.className = 'approve';
  a.innerHTML = `<button class="btn pri sm">${ic('check', 's')}Izinkan</button><button class="btn sm">${ic('x', 's')}Tolak</button>`;
  const [yes, no] = a.querySelectorAll('button');
  const act = ok => { a.remove(); runStream('/api/approval/' + id, {ok}) };
  yes.onclick = () => act(true); no.onclick = () => act(false);
  el.querySelector('.b').append(a);
}
async function runStream(path, body) {
  S.busy = true; $('#sendBtn').disabled = true;
  const th = $('#thread');
  const st = document.createElement('div'); st.className = 'status'; st.setAttribute('role','status'); st.innerHTML = '<span class="spin"></span><span class="activity-label">Menghubungkan AI…</span><small class="activity-elapsed"></small>'; th.append(st);
  const started=Date.now(); const clock=setInterval(()=>{if(!document.hidden)st.querySelector('.activity-elapsed').textContent=Math.floor((Date.now()-started)/1000)+' dtk'},1000);
  $('#chatBackend').disabled=true;$('#chatModel').disabled=true;$('#chatModelApply').disabled=true;
  let draft = null, draftText = '';
  scrollEnd();
  try {
    await stream(path, body, ev => {
      if (ev.type === 'status') { st.querySelector('.activity-label').textContent = ev.data; if (draft) { draft.remove(); draft = null; draftText = '' } }
      else if (ev.type === 'token') {
        st.querySelector('.activity-label').textContent='Menulis jawaban…';
        if (!draft) { draft = addMsg({role: 'assistant', content: ''}); draft.querySelector('.meta').remove(); draft.innerHTML='<div class="b"></div>'; th.append(st) }
        draftText += ev.data; draft.querySelector('.b').innerHTML = md(draftText);
      } else if (ev.type === 'done') {
        if (draft) draft.remove();
        st.remove();
        const d = ev.data; addMsg({role: 'assistant', content: d.text, id: d.message_id, meta: {...(d.meta || {}), approval: d.approval}});
      }
      scrollEnd();
    });
  } catch (e) { addMsg({role: 'assistant', content: 'Koneksi terputus: ' + e.message + '. Jawaban tetap disimpan, muat ulang halaman.'}) }
  clearInterval(clock); st.remove(); S.busy = false; $('#chatBackend').disabled=false;$('#chatModel').disabled=false;$('#chatModelApply').disabled=false; $('#sendBtn').disabled = false; $('#input').focus();
}
async function send() {
  const t = $('#input').value.trim(); const imgs = S.attach.slice();
  if ((!t && !imgs.length) || S.busy) return;
  $('#input').value = ''; autosize(); S.attach = []; renderAttach();
  const body = {text: t, images: imgs};
  if (S.viewChat) { body.chat_id = S.viewChat; S.viewChat = null; $('#oldBar').classList.add('hidden') }
  addMsg({role: 'user', content: t, localImages: imgs}); await runStream('/api/chat/' + S.bot.id, body);
}
/* lampiran gambar: diperkecil di peramban dulu supaya cepat dikirim */
function shrinkImage(file) {
  return new Promise((ok, fail) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, 1280 / Math.max(img.width, img.height));
      const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
      ok(c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); fail(new Error('bukan gambar')) };
    img.src = url;
  });
}
async function addFiles(files) {
  for (const f of [...files].filter(f => f.type.startsWith('image/')).slice(0, 3 - S.attach.length)) {
    try { S.attach.push(await shrinkImage(f)) } catch (e) { toast('Berkas itu bukan gambar') }
  }
  renderAttach();
}
function renderAttach() {
  const row = $('#attachRow'); row.classList.toggle('hidden', !S.attach.length);
  row.innerHTML = S.attach.map((u, i) => `<div class="thumb"><img src="${u}" alt=""><button type="button" data-rm="${i}" aria-label="Hapus">${ic('x', 's')}</button></div>`).join('');
  row.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { S.attach.splice(+b.dataset.rm, 1); renderAttach() });
}
$('#attachBtn').onclick = () => $('#fileIn').click();
$('#fileIn').onchange = e => { addFiles(e.target.files); e.target.value = '' };
$('#input').addEventListener('paste', e => { const fs = [...(e.clipboardData?.files || [])]; if (fs.length) { e.preventDefault(); addFiles(fs) } });
/* riwayat */
async function openHist() {
  if(S.busy)return toast('Tunggu jawaban selesai sebelum membuka riwayat.');
  const d = await api('/api/chats');
  $('#histSub').textContent = 'Semua bot · pilih percakapan untuk membukanya.';
  const day = ts => { const d0 = new Date(ts * 1000), n = new Date(); const diff = Math.floor((new Date(n.toDateString()) - new Date(d0.toDateString())) / 864e5);
    return diff === 0 ? 'Hari ini' : diff === 1 ? 'Kemarin' : diff < 7 ? 'Minggu ini' : d0.toLocaleDateString('id-ID', {month: 'long', year: 'numeric'}) };
  let last = '', html = '';
  for (const c of d.chats) {
    const g = day(c.updated_at); if (g !== last) { html += `<div class="hist-day">${g}</div>`; last = g }
    const on = !c.archived && c.channel === 'web';
    html += `<div class="hist-item ${on ? 'on' : ''}" data-id="${c.id}" data-bot="${esc(c.bot_id)}"><div class="grow"><div class="t">${esc(c.title || 'Percakapan')}</div><div class="sub" style="margin:2px 0 0">${esc(S.bots.find(b=>b.id===c.bot_id)?.name||c.bot_id)} · ${c.channel === 'tg' ? 'Telegram' : 'Web'} · ${c.n} pesan · ${ago(c.updated_at)}${on ? ' · sedang aktif' : ''}</div></div>
      <button class="ib" data-ren="${c.id}" aria-label="Ganti judul" title="Ganti judul">${ic('edit', 's')}</button>
      <a class="ib" href="/api/chats/${c.id}/unduh" aria-label="Unduh" title="Unduh">${ic('download', 's')}</a>
      <button class="ib" data-del="${c.id}" aria-label="Hapus" title="Hapus">${ic('trash', 's')}</button></div>`;
  }
  $('#histList').innerHTML = html || '<p class="muted small">Belum ada riwayat.</p>';
  $$('#histList .hist-item').forEach(x => x.onclick = e => { if (e.target.closest('[data-ren],[data-del],a')) return; $('#histModal').classList.add('hidden'); S.bot=S.bots.find(b=>b.id===x.dataset.bot);refreshBots();loadChat(+x.dataset.id) });
  $$('#histList [data-ren]').forEach(x => x.onclick = async () => { const t = prompt('Judul baru:'); if (t) { await api('/api/chats/' + x.dataset.ren, {method: 'POST', body: {title: t}}); openHist() } });
  $$('#histList [data-del]').forEach(x => x.onclick = async () => { if (confirm('Hapus percakapan ini selamanya?')) { await api('/api/chats/' + x.dataset.del, {method: 'DELETE'}); openHist(); if (S.viewChat == x.dataset.del) loadChat() } });
  $('#histModal').classList.remove('hidden');
}
$('#histBtn').onclick = openHist; $('#histBtn2').onclick = openHist;
$('#histModal').addEventListener('click', e => { if (e.target.id === 'histModal' || e.target.closest('[data-close]')) $('#histModal').classList.add('hidden') });
$('#sendForm').onsubmit = e => { e.preventDefault(); send() };
$('#input').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send() } });
function autosize() { const t = $('#input'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 180) + 'px' }
$('#input').addEventListener('input', autosize);
const newChat = async () => { await api(`/api/chat/${S.bot.id}/reset`, {method: 'POST'}); toast('Percakapan sebelumnya tersimpan di Riwayat'); loadChat() };
$('#newChat').onclick = newChat; $('#newChat2').onclick = newChat;

/* ---------- halaman bot ---------- */
async function loadBots() {
  await refreshBots();
  const label = t => (S.tools.find(x => x.name === t) || {}).label || t;
  $('#botCards').innerHTML = S.bots.map(b => `<div class="card"><div class="row">${av(b, 'l')}<div class="grow"><div class="t">${esc(b.name)}</div><div class="sub" style="margin:0">${b.skills} skill · ingatan ${b.memory_scope === 'own' ? 'sendiri' : 'bersama'}${b.active ? '' : ' · nonaktif'} · ${esc(b.backend||'utama')} · ${esc(b.model||'model utama')}</div></div></div><p class="bot-purpose">${esc(b.persona.slice(0,160))}${b.persona.length>160?'…':''}</p><div class="sub">${b.tools.length} alat tersedia · detail di Ubah</div><div class="row" style="margin-top:4px"><button class="btn sm" data-chat="${b.id}">${ic('chat', 's')}Chat</button><button class="btn sm ghost" data-edit="${b.id}">${ic('edit', 's')}Ubah</button></div></div>`).join('');
  $$('[data-chat]').forEach(x => x.onclick = () => pickBot(x.dataset.chat));
  $$('[data-edit]').forEach(x => x.onclick = () => editBot(S.bots.find(b => b.id === x.dataset.edit)));
}
function editBot(b) {
  const f = $('#botForm'); f.reset();
  $('#botModalTitle').textContent = b ? 'Ubah bot' : 'Bot baru';
  const v = b || {id: '', icon: 'bot', name: '', persona: '', tools: ['web_search', 'read_webpage', 'remember'], memory_scope: 'shared', model: '', telegram_token: ''};
  for (const k of ['id', 'name', 'persona', 'memory_scope', 'model', 'backend', 'telegram_token']) f.elements[k].value = v[k] || '';
  $('#iconPick').innerHTML = BOT_ICONS.map(n => `<label><input type="radio" name="icon" value="${n}" ${n === (v.icon || 'bot') ? 'checked' : ''}>${ic(n)}</label>`).join('');
  $('#toolPick').innerHTML = S.tools.map(t => `<label><input type="checkbox" value="${t.name}" ${v.tools.includes(t.name) ? 'checked' : ''}>${esc(t.label)}</label>`).join('');
  $('#botDel').classList.toggle('hidden', !b);
  $('#botModal').classList.remove('hidden');
  loadBotModelChoices().catch(sayError);
}
$('#addBot').onclick = () => editBot(null);
$('#botModal').addEventListener('click', e => { if (e.target.id === 'botModal' || e.target.closest('[data-close]')) $('#botModal').classList.add('hidden') });
$('#botForm').onsubmit = async e => {
  e.preventDefault(); const f = e.target;
  const body = Object.fromEntries(['id', 'name', 'persona', 'memory_scope', 'model', 'backend', 'telegram_token'].map(k => [k, f.elements[k].value.trim()]));
  if (!body.id) delete body.id;
  body.icon = (f.querySelector('input[name=icon]:checked') || {}).value || 'bot';
  body.tools = $$('#toolPick input:checked').map(x => x.value);
  try { await api('/api/bots', {method: 'POST', body}); $('#botModal').classList.add('hidden'); toast('Bot disimpan'); loadBots() } catch (err) { toast(err.message) }
};
$('#botDel').onclick = async () => {
  const id = $('#botForm').elements.id.value; if (!confirm('Hapus bot ini? Jadwalnya ikut dimatikan.')) return;
  try { await api('/api/bots/' + id, {method: 'DELETE'}); $('#botModal').classList.add('hidden'); S.bot = null; loadBots() } catch (err) { toast(err.message) }
};

/* ---------- ingatan ---------- */
const KIND = {profil: 'tentang Anda', fakta: 'fakta', pelajaran: 'pelajaran', ringkasan: 'ringkasan'};
let memoryPage=0,skillPage=0;
async function loadMem() {
  const q = $('#memQ').value.trim(); const d = await api('/api/memories' + (q ? '?q=' + encodeURIComponent(q) : ''));
  memoryPage=Math.min(memoryPage,Math.max(0,Math.ceil(d.memories.length/8)-1));
  $('#memList').innerHTML = d.memories.slice(memoryPage*8,memoryPage*8+8).map(m => `<div class="r"><div class="grow"><span class="memory-preview">${esc(friendlySteps(m.text).slice(0,180))}</span><button class="btn sm ghost" data-memory-read="${m.id}">Baca lengkap</button><div class="sub">${KIND[m.kind] || esc(m.kind)} · ${m.scope === 'shared' ? 'bersama' : esc((S.bots.find(b => b.id === m.scope) || {name: m.scope}).name)} · dipakai ${m.uses}× · ${ago(m.created_at)}</div></div><button class="ib" data-del="${m.id}" aria-label="Hapus">${ic('trash', 's')}</button></div>`).join('') || empty('Belum ada ingatan. Ceritakan sesuatu tentang Anda di chat, atau tekan Tambah.');
  recordPager($('#memList'),memoryPage,d.memories.length,n=>{memoryPage=n;loadMem()});
  $$('#memList [data-memory-read]').forEach(b=>b.onclick=()=>showDetail('Ingatan', '<pre class=detail-text>'+esc(d.memories.find(m=>m.id===Number(b.dataset.memoryRead)).text)+'</pre>'));
  $$('#memList [data-del]').forEach(x => x.onclick = async () => { await api('/api/memories/' + x.dataset.del, {method: 'DELETE'}); loadMem() });
}
let memT; $('#memQ').oninput = () => { memoryPage=0;clearTimeout(memT); memT = setTimeout(loadMem, 300) };
$('#memAdd').onclick = async () => { const t = prompt('Apa yang perlu diingat agen?'); if (!t) return; await api('/api/memories', {method: 'POST', body: {text: t, kind: 'profil'}}); loadMem() };

/* ---------- skill ---------- */
async function loadSkills() {
  const d = await api('/api/skills'); window.loadedSkills = d.skills;
  skillPage=Math.min(skillPage,Math.max(0,Math.ceil(d.skills.length/8)-1));
  $('#skillList').innerHTML = d.skills.slice(skillPage*8,skillPage*8+8).map(s => `<div class="r"><div class="grow"><div class="row" style="gap:8px"><b>${esc(s.name)}</b>${s.active ? '' : '<span class="tag">mati</span>'}</div><div class="sub">${esc(s.when_to_use)}</div><button class="btn sm ghost" data-skill-read="${s.id}">Baca prosedur</button><div class="sub">${s.scope === 'shared' ? 'bersama' : esc((S.bots.find(b => b.id === s.scope) || {name: s.scope}).name)} · ${s.source === 'manual' ? 'disimpan agen' : s.source === 'bawaan' ? 'bawaan' : 'hasil belajar'} · dipakai ${s.uses}× · ${s.wins} bagus · ${s.fails} kurang · ${ago(s.updated_at)}</div></div><div class="row" style="gap:2px"><button class="btn sm ghost" data-edit-skill="${s.id}">Edit</button><button class="btn sm ghost" data-tog="${s.id}" data-a="${s.active ? 0 : 1}">${s.active ? 'Matikan' : 'Nyalakan'}</button><button class="ib" data-del="${s.id}" aria-label="Hapus">${ic('trash', 's')}</button></div></div>`).join('') || empty('Belum ada skill. Agen menulis skill setelah berhasil mengerjakan tugas beberapa langkah, misalnya mencari lalu menyimpan ke berkas.');
  recordPager($('#skillList'),skillPage,d.skills.length,n=>{skillPage=n;loadSkills()});
  $$('#skillList [data-skill-read]').forEach(b=>b.onclick=()=>{const s=d.skills.find(s=>s.id===Number(b.dataset.skillRead));showDetail(s.name,'<pre class=detail-text>'+esc(friendlySteps(s.steps))+'</pre>')});
  $$('#skillList [data-edit-skill]').forEach(x => x.onclick = () => skillEditor(d.skills.find(s => s.id === Number(x.dataset.editSkill))));
  $$('#skillList [data-tog]').forEach(x => x.onclick = async () => { await api('/api/skills/' + x.dataset.tog, {method: 'POST', body: {active: x.dataset.a === '1'}}); loadSkills() });
  $$('#skillList [data-del]').forEach(x => x.onclick = async () => { if (confirm('Hapus skill ini?')) { await api('/api/skills/' + x.dataset.del, {method: 'DELETE'}); loadSkills() } });
}

/* ---------- jadwal ---------- */
async function loadJobs() {
  const d = await api('/api/jobs');
  $('#jobList').innerHTML = d.jobs.map(j => `<div class="r"><span class="av">${ic(j.kind === 'task' ? 'calendar' : 'bell', 's')}</span><div class="grow">${esc(j.text)}<div class="sub">${j.kind === 'task' ? 'Tugas' : 'Pengingat'} · berikutnya ${ago(j.next_run)}${j.repeat ? ' · diulang ' + esc(j.repeat) : ''} · ${esc((S.bots.find(b => b.id === j.bot_id) || {name: j.bot_id}).name)} · ${j.channel === 'tg' ? 'Telegram' : 'web'}</div>${j.last_result ? `<div class="sub">terakhir: ${esc(j.last_result).slice(0, 160)}</div>` : ''}</div><button class="btn sm ghost danger" data-del="${j.id}">Batalkan</button></div>`).join('') || empty('Tidak ada jadwal aktif.');
  $$('#jobList [data-del]').forEach(x => x.onclick = async () => { await api('/api/jobs/' + x.dataset.del, {method: 'DELETE'}); loadJobs() });
}

/* ---------- model & server ---------- */
const stat = (k, v, pct) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div>${pct != null ? `<div class="bar"><i style="width:${Math.min(100, pct)}%"></i></div>` : ''}</div>`;
async function loadModels() {
  const s = await api('/api/status');
  $('#stats').innerHTML = stat('RAM terpakai', `${(s.ram_used_mb / 1024).toFixed(1)} <span class="small muted">/ ${(s.ram_total_mb / 1024).toFixed(1)} GB</span>`, 100 * s.ram_used_mb / s.ram_total_mb) +
    stat('Agen', `${s.agent_mb} <span class="small muted">MB</span>`) + stat('Beban CPU', `${s.load.split(' ')[0]} <span class="small muted">/ ${s.cpus} inti</span>`) +
    stat('Disk sisa', `${s.disk_free_gb} <span class="small muted">GB</span>`) + stat('Swap', s.swap_total_mb ? `${s.swap_used_mb} <span class="small muted">/ ${s.swap_total_mb} MB</span>` : '<span class="small muted">tidak ada</span>') +
    stat('Di RAM', `<span class="small" style="font-weight:500">${esc(s.loaded.map(x => prettyModel(x.split(' (')[0])).join(', ') || 'kosong')}</span>`);
  const legacyPanels=$('#modelList').closest('.group');legacyPanels.classList.toggle('hidden',s.backend!=='ollama');
  $('#benchPick').closest('.group').classList.toggle('hidden',s.backend!=='ollama');
  $('#modelList').innerHTML = s.installed.map(m => `<div class="r" style="align-items:center"><div class="grow"><b style="font-weight:500">${esc(prettyModel(m.name))}</b><div class="sub">${m.size_gb} GB</div></div>${m.name === s.model ? `<span class="tag on">aktif</span>` : `<button class="btn sm" data-use="${esc(m.name)}">Pakai</button><button class="ib" data-rm="${esc(m.name)}" aria-label="Hapus">${ic('trash', 's')}</button>`}</div>`).join('') || empty('Ollama belum punya model atau tidak terhubung.');
  $$('[data-use]').forEach(x => x.onclick = async () => { await api('/api/settings', {method: 'POST', body: {model: x.dataset.use}}); toast('Model diganti'); loadModels(); sideStatus() });
  $$('[data-rm]').forEach(x => x.onclick = async () => { if (confirm('Hapus model ' + x.dataset.rm + ' dari disk?')) { await api('/api/models/delete', {method: 'POST', body: {name: x.dataset.rm}}); loadModels() } });
  $('#benchPick').innerHTML = s.installed.map(m => `<label><input type="checkbox" value="${esc(m.name)}" ${m.size_gb < 2.3 ? 'checked' : ''}>${esc(prettyModel(m.name))}</label>`).join('');
  loadBench();
}
$('#pullBtn').onclick = async () => {
  const name = $('#pullName').value.trim(); if (!name) return; $('#pullBtn').disabled = true;
  await stream('/api/models/pull', {name}, ev => { $('#pullStatus').textContent = ev.type === 'done' ? ev.data.text : (ev.data || '') });
  $('#pullBtn').disabled = false; loadModels();
};
let benchTimer;
async function loadBench() {
  const d = await api('/api/bench');
  $('#benchRows').innerHTML = d.results.map(r => `<tr><td>${esc(prettyModel(r.model))}</td><td><b>${r.score}</b><span class="muted">/${r.total}</span></td><td>${r.avg_seconds}</td><td>${r.tok_per_sec}</td><td>${r.ram_mb ? r.ram_mb + ' MB' : ''}</td><td class="muted">${ago(r.created_at)}</td><td><button class="btn sm ghost" data-det="${r.id}">Detail</button></td></tr>`).join('') || '<tr><td colspan="7" class="muted">Belum ada hasil uji.</td></tr>';
  $$('[data-det]').forEach(x => x.onclick = () => { const r = d.results.find(y => y.id == x.dataset.det); const det = JSON.parse(r.detail); alert(det.map(t => `${t.ok ? 'Lolos' : 'Gagal'}: ${t.id.replace(/-/g, ' ')} (${t.seconds} dtk), ${t.desc}\n   alat: ${t.calls.join(', ') || 'tidak ada'}\n   jawaban: ${t.answer.slice(0, 140)}`).join('\n\n')) });
  const run = d.running || {}; const log = $('#benchLog');
  if (run.running || (run.log && run.log.length)) { log.classList.remove('hidden'); log.textContent = (run.log || []).join('\n') + (run.running ? `\n… ${run.model} tugas ${run.i}/${run.n}` : ''); log.scrollTop = log.scrollHeight }
  $('#benchBtn').disabled = !!run.running;
  clearTimeout(benchTimer); if (run.running && S.view === 'settings') benchTimer = setTimeout(loadBench, 4000);
}
$('#benchBtn').onclick = async () => {
  const models = $$('#benchPick input:checked').map(x => x.value); if (!models.length) return toast('Pilih minimal satu model');
  try { await api('/api/bench', {method: 'POST', body: {models}}); toast('Uji dimulai'); setTimeout(loadBench, 1500) } catch (e) { toast(e.message) }
};

/* ---------- pengaturan ---------- */
async function loadSettings() {
  const [s, st] = await Promise.all([api('/api/settings'), api('/api/status')]);
  const f = $('#setForm');
  $('#modelSel').value = s.model;
  $('#modelChoices').innerHTML = [...new Set([s.model, "online", ...st.installed.map(m => m.name)])].map(n => `<option value="${esc(n)}" ${n === s.model ? 'selected' : ''}>${esc(prettyModel(n))}</option>`).join('');
  $('#visionSel').innerHTML = `<option value="">Tidak ada</option>` + [...new Set([s.vision_model, ...st.installed.map(m => m.name)].filter(Boolean))].map(n => `<option value="${esc(n)}" ${n === s.vision_model ? 'selected' : ''}>${esc(prettyModel(n))}</option>`).join('');
  for (const k of ['full_access', 'llm_backend', 'compatible_base', 'compatible_key', 'tool_mode', 'telegram_token', 'num_ctx', 'max_steps', 'browser_engine', 'online_base', 'online_key', 'online_model', 'searx_url', 'dns_aman', 'image_gen', 'cpu_hemat']) if (f.elements[k]) f.elements[k].value = s[k] || '';
  f.elements.tg_user_ids.value = (s.tg_user_ids || []).join(', ');
  $('#pairCode').textContent = s.pair_code;
  $('#consol').textContent = st.last_consolidate ? 'Perapian malam terakhir: ' + st.last_consolidate : '';
}
$('#setForm').onsubmit = async e => {
  e.preventDefault(); const f = e.target; const body = {};
  for (const k of ['full_access', 'compatible_base', 'compatible_key', 'tool_mode', 'telegram_token', 'model', 'num_ctx', 'max_steps', 'browser_engine', 'online_base', 'online_key', 'online_model', 'searx_url', 'dns_aman', 'vision_model', 'image_gen', 'cpu_hemat', 'new_password']) body[k] = f.elements[k].value;
  body.tg_user_ids = f.elements.tg_user_ids.value.split(/[,\s]+/).filter(Boolean);
  if (!body.new_password) delete body.new_password;
  try { await api('/api/settings', {method: 'POST', body}); f.elements.new_password.value = ''; toast('Tersimpan'); loadSettings(); sideStatus() } catch (err) { toast(err.message) }
};
$('#logoutBtn').onclick = async () => { await api('/api/logout', {method: 'POST'}); showLogin() };
$('#themeBtn').onclick = () => {
  const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const nx = cur === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = nx; try { localStorage.setItem('tema', nx) } catch (e) {}
};

/* ---------- status & notifikasi ---------- */
async function sideStatus() {
  try {
    const s = await api('/api/status');
    const cls = s.backend==='local'&&!s.runtime?.ready ? (s.runtime?.phase==='failed'?'bad':'busy') : s.backend==='ollama'&&!s.ollama_ok ? 'bad' : s.queue ? 'busy' : 'ok';
    const txt = s.backend==='local' ? 'Lokal · '+(s.runtime?.ready?'siap':s.runtime?.phase==='failed'?'gagal':'belum siap') : s.backend==='ollama'&&!s.ollama_ok ? 'Ollama tidak terhubung' : s.queue ? `Sibuk · ${s.queue} antre` : 'Mode '+s.backend;
    $('#sideStatus').innerHTML = `<span class="dot ${cls}"></span>${txt}`;
    $('#sideRam').textContent = `RAM ${(s.ram_used_mb / 1024).toFixed(1)} / ${(s.ram_total_mb / 1024).toFixed(1)} GB · ${s.backend==='local'?s.local_model_name:s.backend==='auto'?'Smart Router':prettyModel(s.active_model||s.model)}`;
    $('#ver').textContent = s.version;
  } catch (e) {}
}
function listen() {
  const es = new EventSource('/api/events');
  es.onmessage = e => { const ev = JSON.parse(e.data); if(ev.type==='activity'&&typeof showActivity==='function')showActivity(ev); if(ev.type==='office_task'&&typeof updateOfficeTask==='function')updateOfficeTask(ev); if(ev.type==='office_discussion'&&typeof updateOfficeDiscussion==='function')updateOfficeDiscussion(ev); if (ev.type === 'notice') { toast(ev.text.slice(0, 90)); if (S.view === 'chat' && ev.bot === S.bot?.id && ev.channel === 'web' && !S.busy) loadChat() } };
  es.onerror = () => { es.close(); setTimeout(listen, 10000) };
}

async function start() {
  try { await api('/api/me') } catch (e) { return }
  $('#login').classList.add('hidden'); $('#app').classList.remove('hidden');
  await refreshBots(); loadChat(); sideStatus(); setInterval(()=>{if(!document.hidden)sideStatus()}, 15000); listen();
  try { const setup=await api('/api/setup'); $('#setupGuide').classList.toggle('hidden',setup.complete); if(!setup.complete)go('ai'); } catch(e) { toast(e.message); }
}

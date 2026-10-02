"""Owner-only, fixed upstream dashboard mounts for the pinned router images."""
import asyncio
import re
from collections import OrderedDict
from urllib.parse import urlparse
import aiohttp
from aiohttp import web
from . import router, free_router, llm

routes = web.RouteTableDef()
_assets = OrderedDict()
_cache_bytes = 0
MAX_CACHE = 16 * 1024 * 1024


def rewrite(text, kind, content_type):
    prefix = '/apps/' + kind
    if kind == 'free' and 'javascript' in content_type:
        # Vite's build-time BASE_URL and React Router basename in the pinned image.
        text = re.sub(r'(["\x27`])/\1\.replace\(/', lambda m: m[1] + prefix + '/' + m[1] + '.replace(/', text)
        text = re.sub(r'basename:(["\x27`])/\1', lambda m: 'basename:' + m[1] + prefix + '/' + m[1], text)
    elif kind == 'router':
        # Next assets, API fetches and dashboard routes. Leave absolute external OAuth URLs intact.
        text = re.sub(r'(["\x27`])/(api|v1|_next)(?=[/"\x27`?])',
                      lambda m: m[1] + prefix + '/' + m[2], text)
    if 'html' in content_type:
        text = re.sub(r'((?:src|href)=["\x27])/(?!/|apps/)', lambda m: m[1] + prefix + '/', text)
        if kind == 'router':
            bridge = '<script>document.addEventListener("click",function(e){var a=e.target.closest("a[href]");if(!a)return;var u=new URL(a.href,location.href);if(u.origin!==location.origin)return;if(u.pathname.startsWith("/dashboard")||u.pathname.startsWith("/apps/router/dashboard")){e.preventDefault();e.stopImmediatePropagation();if(!u.pathname.startsWith("/apps/router/"))u.pathname="/apps/router"+u.pathname;location.assign(u.href)}},true);</script>'
            text = text.replace('<head>', '<head>' + bridge, 1)
        if kind == 'free':
            # The frontend needs a session marker; the actual admin JWT stays server-side.
            text = text.replace('<head>', '<head><script>localStorage.setItem("freellmapi_dashboard_token","agenmini-owner-session");</script>', 1)
    return text


@routes.get('/apps/{kind}')
async def app_redirect(request):
    if request.match_info['kind'] not in ('router', 'free'): raise web.HTTPNotFound()
    raise web.HTTPFound(request.path + '/')


@routes.route('*', '/apps/{kind}/{tail:.*}')
async def proxy(request):
    global _cache_bytes
    kind, tail = request.match_info['kind'], request.match_info['tail']
    if kind not in ('router', 'free'): raise web.HTTPNotFound()
    if any(p in ('..', '.') for p in tail.split('/')) or '\\' in tail or tail.startswith('/') or ':' in tail:
        raise ValueError('Jalur dashboard tidak valid.')
    path = '/' + tail
    if kind == 'router' and path == '/': raise web.HTTPFound('/apps/router/dashboard')
    base = router.base() if kind == 'router' else free_router.base()
    key = kind + ':' + base + path
    is_asset = path.startswith(('/_next/static/', '/assets/')) and request.method == 'GET'
    if is_asset and key in _assets:
        data, ct = _assets[key]; _assets.move_to_end(key)
        return web.Response(body=data, content_type=None, headers={'Content-Type': ct, 'Cache-Control': 'private, max-age=86400'})
    headers = {k: v for k, v in request.headers.items() if k.lower() in ('accept', 'content-type', 'next-action', 'next-router-state-tree', 'next-router-prefetch', 'rsc')}
    # Cookies, Host, Origin, redirects and credentials cannot leak to an arbitrary upstream.
    url = base + path
    if request.query_string: url += '?' + request.query_string
    try:
        if kind == 'router': headers.update(router.headers())
        elif path.startswith('/api/'):
            await free_router.request('GET', '/api/auth/status')
            headers['Authorization'] = 'Bearer ' + free_router._token
        elif path.startswith('/v1/'):
            headers['Authorization'] = request.headers.get('Authorization') or 'Bearer ' + await free_router.ensure_key()
        if kind == "router" and path.startswith("/v1/") and request.headers.get("Authorization"):
            headers["Authorization"] = request.headers["Authorization"]
        async with llm.session().request(request.method, url, data=await request.read(), headers=headers,
                                        allow_redirects=False, timeout=aiohttp.ClientTimeout(total=180)) as r:
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            response_headers = {'Content-Type': ct, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            if 300 <= r.status < 400:
                loc = r.headers.get('Location', '/')
                parsed = urlparse(loc)
                if parsed.netloc and parsed.netloc != urlparse(base).netloc:
                    raise ValueError('Redirect dashboard keluar dari layanan dibatalkan.')
                response_headers['Location'] = '/apps/' + kind + '/' + (parsed.path or '').lstrip('/') + ('?' + parsed.query if parsed.query else '')
                return web.Response(status=r.status, headers=response_headers)
            if 'event-stream' in ct:
                resp = web.StreamResponse(status=r.status, headers=response_headers); await resp.prepare(request)
                async for chunk in r.content.iter_chunked(32768): await resp.write(chunk)
                return resp
            if any(t in ct for t in ('html', 'javascript', 'css', 'text/x-component')):
                raw = bytearray()
                async for chunk in r.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw) > 8 * 1024 * 1024: raise ValueError('Aset dashboard melebihi batas 8 MB.')
                data = rewrite(raw.decode('utf-8'), kind, ct).encode()
                if is_asset and r.status == 200 and len(data) <= MAX_CACHE:
                    while _assets and _cache_bytes + len(data) > MAX_CACHE:
                        _, (old, _) = _assets.popitem(last=False); _cache_bytes -= len(old)
                    _assets[key] = (data, ct); _cache_bytes += len(data)
                    response_headers['Cache-Control'] = 'private, max-age=86400'
                return web.Response(status=r.status, body=data, headers=response_headers)
            resp = web.StreamResponse(status=r.status, headers=response_headers); await resp.prepare(request)
            async for chunk in r.content.iter_chunked(65536): await resp.write(chunk)
            return resp
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return web.Response(status=503, content_type='text/html', text='<!doctype html><meta name="viewport" content="width=device-width"><title>Layanan disiapkan</title><style>body{font:16px system-ui;padding:32px}i{display:inline-block;width:18px;height:18px;border:2px solid #ddd;border-top-color:#333;border-radius:50%;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}</style><i></i><h2>Dashboard sedang disiapkan</h2><p>Pilih layanan di Koneksi dan tunggu supervisor VPS.</p><button onclick="location.reload()">Coba lagi</button> <a href="/">Kembali ke Agen Mini</a>')

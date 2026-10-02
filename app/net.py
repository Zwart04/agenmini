"""DNS aman (DNS-over-HTTPS) untuk permintaan web agen.

Sebagian jaringan membelokkan DNS biasa (mis. ke halaman blokir), sehingga mesin pencari
tidak bisa dihubungi. Seperti "DNS aman" di Chrome/Firefox, nama situs publik ditanyakan ke
Cloudflare/Google lewat HTTPS. Nama tanpa titik (container Docker seperti Ollama) tetap lewat DNS biasa.
Bisa dimatikan di Pengaturan (dns_aman = 0).
"""
import asyncio
import ipaddress
import socket
import time

import aiohttp
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver

DOH_SERVERS = ["https://1.1.1.1/dns-query", "https://8.8.8.8/resolve"]
_cache: dict[str, tuple[float, list[str]]] = {}


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _local_name(host: str) -> bool:
    return "." not in host or host.endswith((".local", ".internal", ".lan", ".localhost")) or host == "localhost"


async def doh_lookup(host: str) -> list[str]:
    hit = _cache.get(host)
    if hit and hit[0] > time.time():
        return hit[1]
    last = None
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as s:
        for srv in DOH_SERVERS:
            try:
                async with s.get(srv, params={"name": host, "type": "A"},
                                 headers={"accept": "application/dns-json"}) as r:
                    data = await r.json(content_type=None)
                ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
                if ips:
                    ttl = min([a.get("TTL", 300) for a in data["Answer"]] + [600])
                    _cache[host] = (time.time() + max(ttl, 60), ips)
                    return ips
            except Exception as e:
                last = e
    raise OSError(f"DoH gagal untuk {host}: {last}")


class SafeResolver(AbstractResolver):
    def __init__(self):
        self.system = ThreadedResolver()

    async def resolve(self, host, port=0, family=socket.AF_INET):
        if _is_ip(host) or _local_name(host):
            return await self.system.resolve(host, port, family)
        try:
            ips = await doh_lookup(host)
        except OSError:
            return await self.system.resolve(host, port, family)
        return [{"hostname": host, "host": ip, "port": port, "family": socket.AF_INET, "proto": 0,
                 "flags": socket.AI_NUMERICHOST} for ip in ips]

    async def close(self):
        await self.system.close()


async def resolve_ips(host: str) -> list[str]:
    """Dipakai penjaga alamat internal supaya memeriksa IP yang benar-benar akan dihubungi."""
    from . import db
    if _is_ip(host):
        return [host]
    if db.setting("dns_aman") != "0" and not _local_name(host):
        try:
            return await doh_lookup(host)
        except OSError:
            pass
    infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return [i[4][0] for i in infos]

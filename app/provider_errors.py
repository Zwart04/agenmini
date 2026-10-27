"""Bounded, actionable provider failures without exposing raw upstream payloads."""
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Failure:
    kind: str
    message: str
    seconds: int = 60
    provider_scope: bool = False


def describe(payload):
    if hasattr(payload, 'failure'):return payload.failure
    text = (json.dumps(payload, ensure_ascii=True) if isinstance(payload, (dict, list)) else str(payload))[:12000].lower()
    if re.search(r'freeusagelimiterror|free usage limit|free models work in opencode|subscribe to', text):
        return Failure('free_limit', 'Akses gratis dibatasi provider. Gunakan akun/API key yang didukung atau pilih provider lain.', 900, True)
    if re.search(r'invalid[_ .-]?grant|unauthorized|invalid.{0,10}(?:key|token)|api key required|authentication.{0,10}(?:fail|error)|\b40[13]\b', text):
        return Failure('auth', 'Login atau API key ditolak. Periksa akun dan kunci di Koneksi AI.', 300, True)
    if re.search(r'quota|resource_exhausted|rate.?limit|insufficient.{0,6}credit|usage limit|\b429\b', text):
        return Failure('quota', 'Kuota atau batas permintaan model tercapai. Pilih model lain atau tunggu batas provider pulih.', 120)
    if re.search(r'bad_gateway|upstream error|forward to upstream|\b50[234]\b|cannot connect|connection refused', text):
        return Failure('upstream', 'Layanan provider sedang bermasalah. Coba provider lain atau ulangi nanti.', 90, True)
    if re.search(r'timeout|timed out|batas waktu', text):
        return Failure('timeout', 'Provider tidak menjawab tepat waktu. Coba lagi atau pilih model lain.', 60)
    return Failure('request', 'Permintaan belum berhasil. Periksa model, endpoint, dan dukungan provider di Koneksi AI.')

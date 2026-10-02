"""Mata agen: gambar dari pengguna dilihat oleh model penglihatan (vision), lalu isinya diteruskan
sebagai teks ke otak utama. Otak utama (model kecil tanpa vision) tidak pernah menebak isi gambar.
"""
import base64
import io
import time
from pathlib import Path

from . import config, db, llm

_caps: dict[str, set] = {}


class VisionUnavailable(Exception):
    pass


async def capabilities(model: str) -> set:
    if model not in _caps:
        try:
            info = await llm.ollama_post("/api/show", {"model": model}, timeout=20)
        except Exception as e:
            raise VisionUnavailable(f"Otak AI (Ollama) tidak bisa dihubungi, jadi gambar belum bisa dilihat. ({e})")
        if info.get("error"):  # model belum diunduh
            return set()
        _caps[model] = set(info.get("capabilities") or [])
    return _caps[model]


async def pick_model() -> str:
    """Model penglihatan dari Pengaturan; kalau kosong, model aktif dipakai bila ia bisa melihat."""
    for m in (db.setting("vision_model"), db.setting("model")):
        if m and "vision" in await capabilities(m):
            return m
    wanted = db.setting("vision_model") or "qwen3.5:0.8b"
    raise VisionUnavailable(
        f"Model penglihatan belum siap. Unduh dulu di VPS: agen unduh {wanted}, "
        "atau pilih model penglihatan lain di web (Pengaturan).")


def shrink(data: bytes, max_side: int = 896) -> bytes:
    """Perkecil & ubah ke JPEG: gambar besar di CPU 2 core bisa makan menit."""
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def save_upload(data: bytes) -> str:
    """Simpan ke folder kerja (unggahan/...) supaya bisa dilihat lagi di riwayat. Kembalikan jalur relatif."""
    folder = config.WORK_DIR / "unggahan"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.jpg"
    path = folder / name
    path.write_bytes(data)
    try:
        import os
        os.chown(folder, config.KERJA_UID, config.KERJA_GID)
        os.chown(path, config.KERJA_UID, config.KERJA_GID)
    except Exception:
        pass
    return f"unggahan/{name}"


PROMPT = ("Describe this image for someone who cannot see it. Answer in Indonesian, concise: at most 8 short "
          "bullet lines. Cover the main objects and people and what they are doing, the place, and copy the visible "
          "text exactly as written. Only describe what is actually visible. Do not translate, interpret or explain "
          "the text, do not guess brands or names, and write 'tidak jelas' for anything you cannot read.")


async def describe(data: bytes, question: str = "") -> str:
    if db.setting("llm_backend") != "ollama" or db.setting("model") == "online":
        raise VisionUnavailable("Pembacaan gambar saat ini membutuhkan backend Ollama. Mode API hanya mendukung chat teks.")
    model = await pick_model()
    img = shrink(data)
    prompt = PROMPT + (f"\nThe user asks about this image: \"{question}\". Answer that question first, "
                       f"then give the description." if question.strip() else "")
    # RAM VPS kecil: lepas model lain dulu kalau sisa RAM tipis (model utama dimuat ulang otomatis nanti)
    from .browser import mem_available_mb
    if mem_available_mb() < 1600:
        await llm.unload_except(model)
    res = await llm.chat([{"role": "user", "content": prompt, "images": [base64.b64encode(img).decode()]}],
                         model=model, temperature=0.1, max_tokens=350)
    text = (res.get("content") or "").strip()
    if not text:
        raise VisionUnavailable("Model penglihatan tidak menghasilkan deskripsi.")
    return text


def is_image_bytes(data: bytes) -> bool:
    try:
        from PIL import Image
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def work_path(rel: str) -> Path:
    base = config.WORK_DIR.resolve()
    p = (base / rel.lstrip("/")).resolve()
    if base != p and base not in p.parents:
        raise ValueError("di luar folder kerja")
    return p

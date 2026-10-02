"""Pengiriman pesan yang tidak diminta langsung (pengingat, hasil tugas terjadwal) ke Telegram atau web."""
import asyncio

from . import db

# pelanggan web yang sedang membuka halaman: daftar antrean asyncio
web_listeners: set[asyncio.Queue] = set()
telegram_sender = None  # diisi oleh telegram.py: async fn(bot, chat_id, text)


async def push_web(event: dict):
    for q in list(web_listeners):
        try:
            q.put_nowait(event)
        except Exception:
            pass


async def notify(bot_id: str, channel: str, ext_id: str, text: str, save: bool = True):
    bot = db.bot(bot_id) or {"id": bot_id, "name": bot_id}
    if save:
        chat = db.chat_for(bot_id, channel, ext_id)
        db.add_message(chat["id"], "assistant", text, {"proaktif": True})
    if channel == "tg" and telegram_sender:
        await telegram_sender(bot, ext_id, text)
    await push_web({"type": "notice", "bot": bot_id, "channel": channel, "text": text})

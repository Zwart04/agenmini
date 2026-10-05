"""Uji alat web tanpa model: python -m tests.web_tools (di dalam container)."""
import asyncio
import time

from app import browser, main


async def t(label, coro):
    t0 = time.time()
    try:
        r = await coro
        print(f"OK    {label} ({time.time() - t0:.1f} dtk)\n      {str(r)[:300].replace(chr(10), ' | ')}")
    except Exception as e:
        print(f"GAGAL {label} ({time.time() - t0:.1f} dtk): {e}")


async def run():
    main.bootstrap(profile='template')
    await t("cari", browser.search("harga emas antam hari ini"))
    await t("baca biasa", browser.read_page("https://id.wikipedia.org/wiki/Jakarta", "jumlah penduduk"))
    await t("tolak alamat internal", browser.read_page("http://127.0.0.1:8443/sehat"))
    await t("tolak metadata cloud", browser.read_page("http://169.254.169.254/latest/meta-data/"))
    await t("lightpanda fetch", browser._cli_dump(["lightpanda", "fetch", "--block-private-networks", "--dump", "html",
                                                    "https://example.com"]))
    await t("browser buka", browser.browse("uji", "open", "https://example.com"))
    await t("browser klik", browser.browse("uji", "click", target=0))
    await t("browser isi", browser.browse("uji", "open", "https://html.duckduckgo.com/html/"))
    s = browser.pool.sessions.get("uji")
    print("      mesin:", s.engine if s else "-")
    await t("browser ketik", browser.browse("uji", "type", target=0, text="cuaca jakarta"))
    await t("browser kirim", browser.browse("uji", "submit", target=0))
    await t("tutup", browser.browse("uji", "close"))
    await t("chromium buka", _chromium())


async def _chromium():
    s = await browser.pool.get("c", fresh_engine="chromium")
    await s.send("Page.navigate", {"url": "https://example.com"}, session=True)
    await s.wait_ready()
    snap = await s.snapshot()
    await browser.browse("c", "close")
    return snap.get("title")


if __name__ == "__main__":
    asyncio.run(run())

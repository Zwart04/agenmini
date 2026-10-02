"""Uji bagian yang tidak butuh model: pengurai alat, waktu jadwal, penyaring memori. Jalankan: python -m pytest tests"""
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from app import llm, memory, tools  # noqa: E402

N = {"web_search", "read_webpage", "schedule", "remember"}


def test_json_tag():
    c, rest = llm.extract_tool_calls('<tool>{"name": "web_search", "arguments": {"query": "emas"}}</tool>', N)
    assert c == [{"name": "web_search", "arguments": {"query": "emas"}}] and rest == ""


def test_qwen_tool_call_tag():
    c, _ = llm.extract_tool_calls('<tool_call>\n{"name": "web_search", "arguments": {"query": "x"}}\n</tool_call>', N)
    assert c[0]["name"] == "web_search"


def test_lfm_pythonic():
    c, _ = llm.extract_tool_calls('<|tool_call_start|>[web_search(query="harga emas")]<|tool_call_end|>', N)
    assert c == [{"name": "web_search", "arguments": {"query": "harga emas"}}]


def test_bare_pythonic():
    c, _ = llm.extract_tool_calls('[schedule(when="besok 07:00", message="minum obat")]', N)
    assert c[0]["arguments"]["message"] == "minum obat"


def test_qwen_coder_xml():
    txt = "<tool_call>\n<function=read_webpage>\n<parameter=url>\nhttps://a.id\n</parameter>\n</function>\n</tool_call>"
    c, _ = llm.extract_tool_calls(txt, N)
    assert c == [{"name": "read_webpage", "arguments": {"url": "https://a.id"}}]


def test_bare_json_in_fence_and_repair():
    c, rest = llm.extract_tool_calls("Baik.\n```json\n{'name': 'remember', 'arguments': {'fact': 'kucing Mochi',}}\n```", N)
    assert c and c[0]["arguments"]["fact"] == "kucing Mochi"


def test_unknown_tool_is_text():
    c, rest = llm.extract_tool_calls('{"name": "hapus_semua", "arguments": {}}', N)
    assert c == [] and "hapus_semua" in rest


def test_plain_answer():
    c, rest = llm.extract_tool_calls("Ibu kota Jepang adalah Tokyo.", N)
    assert c == [] and rest.startswith("Ibu kota")


def test_strip_think():
    assert llm.strip_think("<think>hmm</think>Jawab") == "Jawab"


def test_parse_when():
    now = datetime.now().astimezone()
    t = datetime.fromtimestamp(tools.parse_when("besok 07.00")).astimezone()
    assert t.hour == 7 and t.minute == 0 and (t.date() - now.date()).days == 1
    assert abs(tools.parse_when("30 menit") - (now.timestamp() + 1800)) < 5
    assert tools.parse_when("2026-12-31 23:59") is not None
    assert tools.parse_when("kapan-kapan") is None


def test_next_repeat():
    assert tools.next_repeat(1000, "daily") == 1000 + 86400
    assert tools.next_repeat(1000, "every 2 hours") == 1000 + 7200
    assert tools.next_repeat(1000, "none") is None


def test_grounded():
    src = "Halo! Kenalkan, nama saya Budi dan saya tinggal di Surabaya."
    assert memory.grounded("Pemilik bernama Budi.", src)
    assert memory.grounded("Pemilik tinggal di Surabaya.", src)
    assert not memory.grounded("Saya ingin menghadiri informasi lebih lanjut", src)


def test_memory_dedupe():
    a, new1 = memory.add_memory("shared", "profil", "Pemilik tinggal di Bandung.")
    b, new2 = memory.add_memory("shared", "profil", "Pemilik tinggal di kota Bandung.")
    assert new1 and not new2 and a == b


def test_skill_save_and_find():
    bot = {"id": "uji-emas", "memory_scope": "shared", "tools": ["web_search"]}
    sid, new = memory.save_skill("uji-emas", "Pantau emas batangan", "saat ditanya harga emas batangan antam",
                                 ["Cari 'harga emas antam hari ini' dengan web_search", "Ambil angka per gram", "Jawab singkat"])
    assert new
    found = [s["id"] for s in memory.search_skills(bot, "harga emas batangan antam berapa?", k=5)]
    assert sid in found
    assert sid not in [s["id"] for s in memory.search_skills(bot, "resep nasi goreng", k=5)]
    assert not memory.search_skills({"id": "uji-emas", "tools": []}, "harga emas batangan antam")

#!/bin/bash
# Uji langsung dengan model sungguhan: gambar masuk, buat gambar, grafik, riwayat. Pakai: uji-langsung.sh <langkah>
BASE=https://127.0.0.1:8443
J=/tmp/agen-uji-cookie
cd ~/agen-uji
login() { curl -sk -c $J -H 'Content-Type: application/json' -d '{"password":"ujicoba123"}' $BASE/api/login >/dev/null; }
tanya() {  # tanya <bot> <berkas-json>
  curl -sk -N -b $J -H 'Content-Type: application/json' --data-binary @"$2" $BASE/api/chat/$1 | python3 -c '
import sys, json, time
t0 = time.time()
for line in sys.stdin:
    ev = json.loads(line)
    if ev.get("type") == "status": print("  ·", ev["data"], f"({time.time()-t0:.0f} dtk)", flush=True)
    elif ev.get("type") == "done":
        d = ev["data"]; m = d.get("meta", {})
        print("\nJAWABAN:", d["text"]); print("  alat:", m.get("tools"), "| berkas:", m.get("files"), "| mode:", m.get("mode"), "|", m.get("seconds"), "dtk")
'
}
json_teks() { python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$1" > /tmp/q.json; }
case "$1" in
  nyala)
    docker compose up -d 2>&1 | tail -1; sleep 6; curl -sk $BASE/sehat; echo ;;
  gambar)
    login
    docker run --rm -v "/mnt/c/Users/Zwart/Downloads/Hasil AI":/in:ro -v /tmp:/out --entrypoint python agenmini:latest -c '
from PIL import Image
im = Image.open("/in/WhatsApp Image 2026-09-29 at 15.49.58 (1).jpeg")
im.crop((178, 232, 697, 780)).save("/out/kopi.jpg", quality=90)
print("foto dipotong", im.size, "->", Image.open("/out/kopi.jpg").size)'
    python3 -c 'import json,base64; print(json.dumps({"text":"jelaskan apa saja yang ada di gambar ini","images":["data:image/jpeg;base64,"+base64.b64encode(open("/tmp/kopi.jpg","rb").read()).decode()]}))' > /tmp/q.json
    tanya asisten /tmp/q.json
    json_teks "tulisan apa saja yang ada di spanduk biru di gambar tadi?"; tanya asisten /tmp/q.json ;;
  tanpagambar)
    login; json_teks "jelaskan apa saja yang ada di gambar ini"; tanya riset /tmp/q.json ;;
  buatgambar)
    login; json_teks "buatkan gambar kucing oren lucu sedang minum kopi di warung"; tanya asisten /tmp/q.json ;;
  grafik)
    login; json_teks "buatkan grafik batang penjualan: Januari 10, Februari 15, Maret 12, lalu kirim grafiknya ke saya"; tanya asisten /tmp/q.json ;;
  riwayat)
    login
    curl -sk -b $J -X POST $BASE/api/chat/asisten/reset >/dev/null
    curl -sk -b $J "$BASE/api/chats?bot=asisten" | python3 -c 'import sys,json; [print("  ", c["id"], c["channel"], c["n"], "pesan |", c["title"], "| arsip" if c["archived"] else "| aktif") for c in json.load(sys.stdin)["chats"]]'
    ID=$(curl -sk -b $J "$BASE/api/chats?bot=asisten" | python3 -c 'import sys,json; print(json.load(sys.stdin)["chats"][0]["id"])')
    echo "  unduh percakapan $ID:"; curl -sk -b $J "$BASE/api/chats/$ID/unduh" | head -8 ;;
esac

#!/bin/bash
# Uji cepat: masuk lalu kirim satu pesan ke bot. Pakai: tests/chat.sh <bot> "<pesan>"
BASE=${BASE:-https://127.0.0.1:8443}
PW=${PW:-ujicoba123}
JAR=/tmp/agen-cookie
curl -sk -c $JAR -H 'Content-Type: application/json' -d "{\"password\":\"$PW\"}" $BASE/api/login >/dev/null
BOT=$1; shift
MSG=$(python3 -c 'import json,sys;print(json.dumps({"text":sys.argv[1]}))' "$*")
curl -sk -N -b $JAR -H 'Content-Type: application/json' -d "$MSG" $BASE/api/chat/$BOT | python3 -c '
import sys, json
tok = False
for line in sys.stdin:
    ev = json.loads(line)
    if "type" not in ev: print("  galat:", ev); continue
    if ev["type"] == "status": print("  ·", ev["data"], flush=True)
    elif ev["type"] == "approval": print("  ⚠ IZIN:", ev["data"], flush=True)
    elif ev["type"] == "done":
        d = ev["data"]; m = d.get("meta", {})
        print("\n" + d["text"]); print("\n  [alat=%s %ss stats=%s]" % (m.get("tools"), m.get("seconds"), m.get("stats")))
'

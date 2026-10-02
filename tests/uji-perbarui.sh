#!/bin/bash
# Uji jalur pembaruan 0.1 -> 0.2 persis seperti di VPS (dijalankan sebagai root di WSL).
set -u
SP="/mnt/c/Users/Zwart/AppData/Local/Temp/claude/C--Users-Zwart-Downloads-Claude-Code/278f2cbc-5b5f-44cf-a5b5-ca0682413a20/scratchpad"
NEW="/mnt/c/Users/Zwart/Downloads/Coding AI/agenmini/dist/pasang.sh"
B=https://127.0.0.1
(cd /home/zwart/agen-uji && docker compose down >/dev/null 2>&1); docker rm -f agen-ui >/dev/null 2>&1
echo "== 1. pasang versi 0.1"
rm -rf /tmp/v01 && mkdir /tmp/v01 && python3 -c "import zipfile; zipfile.ZipFile('$SP/agenmini-v0.1.0.zip').extractall('/tmp/v01')"
AGEN_OTOMATIS=1 bash /tmp/v01/agenmini/dist/pasang.sh > /tmp/v01.log 2>&1; echo "   selesai (exit $?)"
PW=$(grep "Kata sandi" /tmp/v01.log | sed 's/\x1b\[[0-9;]*m//g' | awk '{print $4}')
curl -sk -c /tmp/jv -H 'Content-Type: application/json' -d "{\"password\":\"$PW\"}" $B/api/login >/dev/null
echo "== 2. isi data di 0.1: percakapan, 'percakapan baru', percakapan lagi"
docker exec agenmini python -c "
from app import db
import time
c = db.chat_for('asisten', 'web', 'web')
db.add_message(c['id'], 'user', 'Harga emas hari ini berapa?'); db.add_message(c['id'], 'assistant', 'Rp 1.987.000 per gram')
time.sleep(1.1); db.run('UPDATE chats SET reset_at=?, summary=\'\' WHERE id=?', (time.time(), c['id'])); time.sleep(1.1)
db.add_message(c['id'], 'user', 'Ingatkan saya rapat jam 9'); db.add_message(c['id'], 'assistant', 'Siap, dijadwalkan.')
print('   pesan di 0.1:', db.one('select count(*) n from messages')['n'], '| baris chat:', db.one('select count(*) n from chats')['n'])
"
echo "== 3. perbarui ke 0.2"
cp "$NEW" /root/pasang.sh && AGEN_OTOMATIS=1 bash /root/pasang.sh > /tmp/v02.log 2>&1; echo "   selesai (exit $?)"
sed 's/\x1b\[[0-9;]*m//g' /tmp/v02.log | grep -E "mode PERBARUI|penglihatan|menyala|GAGAL" | sed 's/^/   /'
echo "== 4. periksa hasil"
docker exec agenmini python -c "
from app import db, VERSION
print('   versi:', VERSION)
for c in db.q('select id, title, archived, (select count(*) from messages m where m.chat_id=chats.id) n from chats order by id'):
    print('   percakapan', c['id'], '|', c['title'], '|', c['n'], 'pesan |', 'riwayat' if c['archived'] else 'aktif')
print('   alat asisten punya gambar:', all(t in db.bot('asisten')['tools'] for t in ('generate_image', 'send_file')))
print('   ingatan Davdigi:', db.one(\"select kind from memories where text like 'Pemilik menjalankan Davdigi%'\")['kind'])
print('   model penglihatan:', db.setting('vision_model'))
"
curl -sk -b /tmp/jv "$B/api/chats?bot=asisten" | python3 -c 'import sys,json; print("   API riwayat:", len(json.load(sys.stdin)["chats"]), "percakapan")'
echo "== 5. bersihkan"
printf "YA\nHAPUS\n" | agen hapus >/dev/null 2>&1; rm -rf /tmp/v01 /tmp/v01.log /tmp/v02.log /root/pasang.sh /tmp/jv
ls /opt/agenmini 2>/dev/null || echo "   /opt/agenmini sudah bersih"

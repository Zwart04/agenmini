#!/usr/bin/env bash
set -euo pipefail
[[ "${AGEN_INSTALLER_TEST_CONTAINER:-0}" == 1 && -f /.dockerenv ]] || exit 2
mkdir -p /mock /opt/agenmini/app /opt/agenmini/data
cp /src/agen-supervisor.sh /opt/agenmini/
cp /src/app/__init__.py /opt/agenmini/app/
touch /opt/agenmini/.env
cat > /mock/docker <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> /tmp/compose-calls
if [[ "$*" == *'python -m app.model_runtime plan'* && "${MOCK_PLAN:-0}" == 1 ]]; then
 echo '{"mode":"local","local":true,"router":false,"free":false,"model":"qwenpaw-2b"}'
elif [[ "$*" == *'ps --status running -q local'* && "${MOCK_RUNNING:-0}" == 1 ]]; then echo test-local
elif [[ "$*" == *'python -m app.local_models qwenpaw-2b'* ]]; then
 echo '{"min_ram_gb":1,"runtime_mb":10,"repo":"fixture/test","file":"fixture.gguf"}'
elif [[ "$*" == *'python -m app.local_models'* ]]; then exit 2; fi
EOF
cat > /mock/curl <<'EOF'
#!/bin/bash
OUT=''
URL=''
while [[ $# -gt 0 ]]; do
 if [[ "$1" == -o ]]; then shift; OUT="$1";
 elif [[ "$1" == https:* ]]; then URL="$1"; fi
 shift
done
if [[ "$URL" == *releases/latest ]]; then
 if [[ "${MOCK_NEW:-0}" == 1 ]]; then
   echo '{"tag_name":"v0.3.3","assets":[{"name":"pasang-vps.sh","browser_download_url":"https://github.com/Zwart04/agenmini/releases/download/v0.3.3/pasang-vps.sh"},{"name":"pasang-vps.sha256","browser_download_url":"https://github.com/Zwart04/agenmini/releases/download/v0.3.3/pasang-vps.sha256"}]}' > "$OUT"
 else echo '{"tag_name":"v0.3.2"}' > "$OUT"; fi
elif [[ "$URL" == *.sha256 ]]; then printf '%064d  pasang-vps.sh\n' 0 > "$OUT"
else echo 'echo must-not-run' > "$OUT"; fi
EOF
chmod +x /mock/*
export PATH=/mock:$PATH
cd /opt/agenmini
echo api > data/runtime-request
echo working > data/task-busy
bash agen-supervisor.sh
[[ -f data/runtime-request ]]
rm data/task-busy
bash agen-supervisor.sh
[[ ! -f data/runtime-request ]]
grep -q 'up -d router' /tmp/compose-calls
jq -e '.ram_mb>0 and .cpus>0' data/hardware.json >/dev/null
echo qwenpaw-2b > data/local-model-request
echo local > data/runtime-request
bash agen-supervisor.sh
grep -q 'LOCAL_REPO=fixture/test' data/local-runtime.env
grep -q 'up -d local' /tmp/compose-calls
BEFORE=$(grep -c 'stop local' /tmp/compose-calls)
echo api > data/runtime-request
MOCK_PLAN=1 MOCK_RUNNING=1 bash agen-supervisor.sh
[[ $(grep -c 'stop local' /tmp/compose-calls) == "$BEFORE" ]]
echo invalid-model > data/local-model-request
echo local > data/runtime-request
bash agen-supervisor.sh
grep -q 'tidak dikenal' data/runtime-status.json
echo check > data/update-request
bash agen-supervisor.sh
grep -q 'sudah terbaru' data/update-status.json
echo install > data/update-request
if MOCK_NEW=1 bash agen-supervisor.sh; then echo 'bad checksum accepted';exit 1;fi
grep -q 'Checksum release tidak cocok' data/update-status.json
! grep -q 'must-not-run' data/update-status.json
echo 'PASS: hardware detection, busy deferral, runtime switch, model allowlist, version check, checksum rejection.'

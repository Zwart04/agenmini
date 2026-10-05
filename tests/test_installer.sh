#!/usr/bin/env bash
# Only for a disposable container; never run on the host.
set -euo pipefail
[[ "${AGEN_INSTALLER_TEST_CONTAINER:-0}" == 1 && -f /.dockerenv ]] || exit 2
mkdir -p /mock /etc/systemd/system
cat > /mock/apt-get <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> /tmp/apt-calls
if [[ "$*" == *docker-ce* ]]; then cp /mock/docker-template /mock/docker; chmod +x /mock/docker; fi
EOF
cat > /mock/docker-template <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> /tmp/docker-calls
if [[ "${MOCK_FAIL:-0}" == 1 && "$*" == *"up -d --build"* ]]; then exit 1; fi
if [[ "$*" == *'python -m app.model_runtime plan'* ]]; then echo '{"mode":"router","local":false,"router":true,"free":false}'; fi
exit 0
EOF
cat > /mock/curl <<'EOF'
#!/bin/bash
if [[ "$*" == *api.ipify.org* ]]; then echo 203.0.113.7
elif [[ "$*" == *"/gpg"* ]]; then
  while [[ $# -gt 0 ]]; do if [[ "$1" == -o ]]; then shift; echo key > "$1"; break; fi; shift; done
else echo '{"ok":true}'; fi
EOF
cat > /mock/systemctl <<'EOF'
#!/bin/bash
exit 0
EOF
cat > /mock/openssl <<'EOF'
#!/bin/bash
echo aabbccddeeff001122334455
EOF
cat > /mock/ss <<'EOF'
#!/bin/bash
exit 0
EOF
chmod +x /mock/*
export PATH=/mock:$PATH AGEN_OTOMATIS=1 AGEN_AI_PROFILE=router
bash /src/dist/pasang-vps.sh > /tmp/install-output
[[ -f /opt/agenmini/app/main.py && -f /opt/agenmini/.env ]]
grep -q 'TERPASANG' /tmp/install-output
grep -q 'docker-ce' /tmp/apt-calls
grep -q 'LLM_BACKEND=router' /opt/agenmini/.env
grep -q 'http://router:20128/v1' /opt/agenmini/.env
[[ $(stat -c '%a' /opt/agenmini/.env) == 600 ]]
[[ -f /opt/agenmini/frontend/index.html && -f /opt/agenmini/frontend/app.js ]]
mkdir -p /opt/agenmini/app/static
echo legacy-design > /opt/agenmini/app/static/custom.css
echo legacy-guide > /opt/agenmini/DESIGN.md
echo keep-me > /opt/agenmini/data/marker
printf '\nCUSTOM_SETTING=keep\n' >> /opt/agenmini/.env
bash /src/dist/pasang-vps.sh > /tmp/update-output
[[ ! -d /opt/agenmini/app/static && ! -f /opt/agenmini/DESIGN.md ]]
find /opt/agenmini/data/backup -path '*/legacy-static/custom.css' -exec grep -q legacy-design {} \; -print | grep -q .
grep -q 'keep-me' /opt/agenmini/data/marker
grep -q 'CUSTOM_SETTING=keep' /opt/agenmini/.env
if MOCK_FAIL=1 bash /src/dist/pasang-vps.sh > /tmp/fail-output 2>&1; then echo 'Build failure was swallowed'; exit 1; fi
if grep -q 'TERPASANG' /tmp/fail-output; then exit 1; fi
# Exercise the actual installer while Bash is reading the file it replaces.
# The long tail forces additional reads after the installer has finished.
for caller in /opt/agenmini/agen-supervisor.sh /usr/local/bin/agen; do
  {
    printf '#!/bin/bash\nset -euo pipefail\nbash /src/dist/pasang-vps.sh > /tmp/live-update-output\n'
    for n in $(seq 1 1000); do printf '# original caller tail %080d\n' "$n"; done
    printf 'echo completed > /tmp/live-update-completed\n'
  } > "$caller"
  OLD_INODE=$(stat -c '%i' "$caller")
  rm -f /tmp/live-update-completed
  bash "$caller"
  [[ $(stat -c '%i' "$caller") != "$OLD_INODE" ]]
  grep -q completed /tmp/live-update-completed
  grep -q TERPASANG /tmp/live-update-output
  grep -q keep-me /opt/agenmini/data/marker
done
# Fresh FreeLLMAPI setup must not start 9router. Isolated fixture only.
rm -rf /opt/agenmini
: > /tmp/docker-calls
AGEN_AI_PROFILE=free bash /src/dist/pasang-vps.sh > /tmp/free-install-output
grep -q 'LLM_BACKEND=freellmapi' /opt/agenmini/.env
# Mock plan controls runtime independently of the fresh env.
! grep -q 'profile router up -d --build' /tmp/docker-calls
rm -rf /opt/agenmini
unset AGEN_AI_PROFILE
bash /src/dist/pasang-vps.sh > /tmp/online-install-output
grep -q 'LLM_BACKEND=online' /opt/agenmini/.env
echo 'PASS: install, preserve data/config, failure handling, atomic updates of running supervisor and CLI.'

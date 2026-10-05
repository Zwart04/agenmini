#!/usr/bin/env bash
# Host commands mocked in a disposable Linux container; never alters host swap.
set -euo pipefail
[[ ${AGEN_INSTALLER_TEST_CONTAINER:-0} == 1 && -f /.dockerenv ]] || exit 2
mkdir -p /mock /opt/agenmini/data /opt/agenmini/app
cp /src/agen-supervisor.sh /src/agen-swap.sh /opt/agenmini/
cp /src/app/__init__.py /opt/agenmini/app/
cat > /mock/swapon <<'EOF'
#!/bin/bash
if [[ "$1" == --show ]]; then [[ ${SWAP_ACTIVE:-0} == 0 ]] || echo /user/swap;exit 0;fi
[[ ${SWAP_FAIL:-0} == 0 ]]
EOF
cat > /mock/fallocate <<'EOF'
#!/bin/bash
echo allocation > "${@: -1}"
EOF
cat > /mock/mkswap <<'EOF'
#!/bin/bash
exit 0
EOF
cat > /mock/docker <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> /tmp/host-compose-calls
if [[ "$*" == *'config --format json'* ]]; then echo '{"services":{"agen":{"mem_limit":838860800}}}';fi
EOF
chmod +x /mock/*;export PATH=/mock:$PATH
echo '# user fstab' > /tmp/agenmini-fstab-test
SWAP_ACTIVE=1 bash /src/agen-swap.sh 2
[[ ! -e /tmp/agenmini-swap-test/swapfile ]]
if SWAP_FAIL=1 bash /src/agen-swap.sh 2;then exit 1;fi
[[ ! -e /tmp/agenmini-swap-test/swapfile && ! -e /tmp/agenmini-swap-test/swapfile.pending ]]
[[ $(cat /tmp/agenmini-fstab-test) == '# user fstab' ]]
bash /src/agen-swap.sh 2
[[ $(stat -c %a /tmp/agenmini-swap-test/swapfile) == 600 ]]
grep -q '^/tmp/agenmini-swap-test/swapfile none swap sw 0 0$' /tmp/agenmini-fstab-test
if bash /src/agen-swap.sh 4;then exit 1;fi
cd /opt/agenmini
printf 'AGEN_MEM_LIMIT=800m\nCUSTOM=keep\n' > .env
printf '{"swap_gb":0,"harness_memory":true,"retry":"omp"}' > data/host-setup-request.json
touch data/harness-run-busy
bash agen-supervisor.sh
[[ -f data/host-setup-request.json ]];! grep -q 'up -d --force-recreate agen' /tmp/host-compose-calls
rm data/harness-run-busy
echo no > data/update-enabled
bash agen-supervisor.sh
grep -q '^AGEN_MEM_LIMIT=2g$' .env;grep -q '^CUSTOM=keep$' .env
[[ $(cat data/harness-resume) == omp && ! -f data/host-setup-request.json ]]
grep -q 'up -d --force-recreate agen' /tmp/host-compose-calls
printf '{"swap_gb":2,"harness_memory":true,"retry":"../../shell"}' > data/host-setup-request.json
if bash agen-supervisor.sh;then exit 1;fi
[[ ! -f data/host-setup-request.json ]]
echo 'PASS fixed host requests, idle-only restart, existing swap preservation, activation failure cleanup and private swap permissions.'

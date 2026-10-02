#!/bin/bash
# Siapkan lingkungan uji di WSL: salin kode, bangun image, nyalakan Ollama uji (2 core), unduh model.
# Hapus lagi dengan tests/bersih-wsl.sh.
SRC="/mnt/c/Users/Zwart/Downloads/Coding AI/agenmini"
mkdir -p ~/agen-uji
rsync -a --delete --exclude __pycache__ --exclude data "$SRC/" ~/agen-uji/
cd ~/agen-uji
docker network create agentest >/dev/null 2>&1
docker run -d --name ollama-test --network agentest --cpus 2 --memory 3600m -v ollama-test:/root/.ollama ollama/ollama:latest >/dev/null 2>&1 || docker start ollama-test
printf "OLLAMA_URL=http://ollama-test:11434\nOLLAMA_NETWORK=agentest\nWEB_PORT=8443\nWEB_PASSWORD=ujicoba123\nMODEL=hf.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M\nPUBLIC_IP=127.0.0.1\n" > .env
docker compose build 2>&1 | tail -2
for m in qwen3.5:0.8b hf.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M; do
  docker exec ollama-test ollama pull "$m" >/dev/null 2>&1 && echo "OK $m" || echo "GAGAL $m"
done
docker exec ollama-test ollama show qwen3.5:0.8b | sed -n '/Capabilities/,/^$/p'

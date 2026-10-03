FROM python:3.12-slim-trixie

# CHROMIUM=0 untuk image lebih kecil (±400 MB lebih hemat disk); browser cadangan jadi tidak ada.
ARG CHROMIUM=1
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data TZ=Asia/Jakarta \
    LIGHTPANDA_DISABLE_TELEMETRY=true PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl openssl tzdata jq procps tini git nodejs npm \
    $( [ "$CHROMIUM" = "1" ] && echo chromium fonts-liberation fonts-noto-color-emoji ) \
 && rm -rf /var/lib/apt/lists/*

# Lightpanda: browser ringan khusus agen (tidak wajib; kalau gagal diunduh, agen tetap jalan)
RUN arch="$(uname -m)" \
 && (curl -fsSL --retry 3 -o /usr/local/bin/lightpanda \
      "https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-${arch}-linux" \
     && chmod +x /usr/local/bin/lightpanda && /usr/local/bin/lightpanda version) \
 || (rm -f /usr/local/bin/lightpanda; echo "PERINGATAN: Lightpanda tidak terpasang")

# User 'kerja': semua perintah/Python/browser dari agen berjalan sebagai user ini
RUN groupadd -g 1001 kerja && useradd -u 1001 -g 1001 -M -d /data/ruang-kerja -s /bin/bash kerja

COPY requirements.lock /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY app /app/app
COPY frontend /app/frontend
WORKDIR /app

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
  CMD curl -fsk https://127.0.0.1:8443/sehat || curl -fs http://127.0.0.1:8443/sehat || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "app.main"]
